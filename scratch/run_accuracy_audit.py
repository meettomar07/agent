import json
import sqlite3
import time
import re
from pathlib import Path
from datetime import datetime, timezone

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.classification.classifier import NoticeCategory, NoticeClassifier
from testkart_intelligence.scheduler.job_runner import ScanScheduler, SchedulerAlreadyRunningError
from testkart_intelligence.discovery.engine import DiscoveryEngine

db_file = Path("data/independent_audit.db")
if db_file.exists():
    db_file.unlink()

init_db(db_file)
with get_db(db_file) as conn:
    seed_sources_if_empty(conn)
    # Seed 3 parent notices for child corrigenda linking
    # 1. SSC JE Parent
    conn.execute(
        """
        INSERT INTO canonical_notices (
            id, source_id, authority_name, notice_number, title,
            normalized_url, category, state, classification, status,
            published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
        ) VALUES (
            'cn_parent_ssc_je', 'src_ssc', 'Staff Selection Commission', 'HQ-EC033/7/2025-EC',
            'Junior Engineer (Civil, Mechanical & Electrical) Examination, 2026 Notification',
            'https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/JE_2026_Notice.pdf',
            'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
            '2026-06-01', 'CURRENT', 'NONE', '2026-06-01T06:00:00Z', '2026-06-01T06:00:00Z'
        )
        """
    )
    # 2. UPSC APP Parent
    conn.execute(
        """
        INSERT INTO canonical_notices (
            id, source_id, authority_name, notice_number, title,
            normalized_url, category, state, classification, status,
            published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
        ) VALUES (
            'cn_parent_upsc_app', 'src_upsc', 'Union Public Service Commission', 'Advt. No. 01/2026',
            'Recruitment Notice Advt. No. 01/2026 for 140 Posts of Assistant Public Prosecutor',
            'https://www.upsc.gov.in/recruitment/advt_01_2026_app.pdf',
            'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
            '2026-01-15', 'CURRENT', 'NONE', '2026-01-15T06:00:00Z', '2026-01-15T06:00:00Z'
        )
        """
    )
    # 3. UPPSC Combined State Parent
    conn.execute(
        """
        INSERT INTO canonical_notices (
            id, source_id, authority_name, notice_number, title,
            normalized_url, category, state, classification, status,
            published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
        ) VALUES (
            'cn_parent_uppsc_combined_state', 'src_uppsc', 'Uttar Pradesh Public Service Commission', 'A-1/E-1/2026',
            'Combined State / Upper Subordinate Services Examination, 2026 Advt. No. A-1/E-1/2026',
            'https://uppsc.up.nic.in/OuterPages/advt_combined_state_2026.html',
            'PSC', 'Uttar Pradesh', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
            '2026-01-01', 'CURRENT', 'NONE', '2026-01-01T06:00:00Z', '2026-01-01T06:00:00Z'
        )
        """
    )

# Load Ground Truth
gt_data = json.loads(Path("INDEPENDENT_ACCURACY_AUDIT_GROUND_TRUTH.json").read_text(encoding="utf-8"))
manifest_data = json.loads(Path("INDEPENDENT_ACCURACY_AUDIT_MANIFEST.json").read_text(encoding="utf-8"))
docs = manifest_data["documents"]

verifier = VerificationAgent(db_path=db_file)
writer = WritingAgent(db_path=db_file)
qa = QualityAssuranceAgent(db_path=db_file)

audit_records = []

for filename, meta in docs.items():
    aid = meta["audit_id"]
    source_id = meta["source_id"]
    authority = meta["authority"]
    title = meta["title"]
    url = meta["source_url"]
    local_path = Path(meta["local_path"])
    doc_bytes = local_path.read_bytes()
    ctype = meta["content_type"]
    
    gt_item = gt_data[filename]
    
    # 1. Ingest canonical notice
    canonical_id = f"cn_{aid}"
    with get_db(db_file) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                canonical_id,
                source_id,
                authority,
                gt_item.get("official_notice_number", aid),
                title,
                url,
                "Central" if "Public Service" in authority or "Staff" in authority or "National" in authority else "State",
                "Central" if "Tamil" not in authority and "Uttar" not in authority else ("Tamil Nadu" if "Tamil" in authority else "Uttar Pradesh"),
                "OTHER_ANNOUNCEMENT",
                "DISCOVERED",
                "2026-10-29",
                "CURRENT",
                "NONE",
                "2026-10-29T17:45:00Z",
                "2026-10-29T17:45:00Z",
            ),
        )

    # 2. Process & Verify via VerificationAgent
    v_id, facts_list = verifier.process_and_verify_document(
        notice_id=canonical_id,
        doc_bytes=doc_bytes,
        doc_url=url,
        content_type=ctype,
    )

    # 3. Read back classification and parent linking
    with get_db(db_file) as conn:
        cn_row = conn.execute(
            "SELECT classification, parent_notice_id, relation_type, relation_confidence, triage_flag FROM canonical_notices WHERE id = ?",
            (canonical_id,),
        ).fetchone()
        pred_class = cn_row["classification"]
        pred_parent = cn_row["parent_notice_id"]
        pred_rel_type = cn_row["relation_type"]
        pred_rel_conf = cn_row["relation_confidence"]
        pred_triage = cn_row["triage_flag"]

        # Fetch all extracted facts
        fact_rows = conn.execute(
            "SELECT fact_key, fact_value, evidence_text, page_number, confidence, verified_status FROM extracted_facts WHERE notice_version_id = ?",
            (v_id,),
        ).fetchall()
        extracted_facts_map = {r["fact_key"]: dict(r) for r in fact_rows}

    # 4. Generate Article Draft
    art_id, art_v_id, content_hash = writer.draft_article(canonical_id)

    # 5. QA Evaluation
    qa_pass, qa_score, qa_checks = qa.inspect_and_evaluate(art_v_id)

    with get_db(db_file) as conn:
        art_row = conn.execute("SELECT template_type, slug FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        v_row = conn.execute("SELECT content_markdown, title FROM article_versions WHERE id = ?", (art_v_id,)).fetchone()
        article_text = v_row["content_markdown"]
        template_type = art_row["template_type"]

    audit_records.append({
        "audit_id": aid,
        "filename": filename,
        "source_id": source_id,
        "authority": authority,
        "title": title,
        "ground_truth": gt_item,
        "prediction": {
            "canonical_id": canonical_id,
            "version_id": v_id,
            "classification": pred_class,
            "parent_notice_id": pred_parent,
            "relation_type": pred_rel_type,
            "relation_confidence": pred_rel_conf,
            "triage_flag": pred_triage,
            "extracted_facts": extracted_facts_map,
            "article_id": art_id,
            "article_version_id": art_v_id,
            "template_type": template_type,
            "qa_score": qa_score,
            "qa_pass": qa_pass,
            "article_markdown": article_text,
        }
    })
    print(f"[{aid}] {authority[:10]} | GT Class: {gt_item['notice_type']:<22} | Pred Class: {pred_class:<22} | QA: {qa_score:5.1f} | Parent: {pred_parent or 'None'}")

# Save full results
with open("data/independent_accuracy_audit_results.json", "w", encoding="utf-8") as f:
    json.dump(audit_records, f, indent=2)

print("\nIngestion and extraction complete. Saved: data/independent_accuracy_audit_results.json")
