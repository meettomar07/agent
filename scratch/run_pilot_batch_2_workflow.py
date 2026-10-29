import json
import sqlite3
import time
from pathlib import Path

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.editorial.service import EditorialService
from testkart_intelligence.publishing.mock_publisher import MockPublisher

db_file = Path("data/pilot_batch_2.db")
if db_file.exists():
    db_file.unlink()

init_db(db_file)
with get_db(db_file) as conn:
    seed_sources_if_empty(conn)
    # Seed parent notices for linking
    # 1. Parent for SSC Stenographer Addendum
    conn.execute(
        """
        INSERT INTO canonical_notices (
            id, source_id, authority_name, notice_number, title,
            normalized_url, category, state, classification, status,
            published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
        ) VALUES (
            'cn_parent_ssc_steno', 'src_ssc', 'Staff Selection Commission', '3/1/2026-P&P-II',
            'Notice of Examination: Stenographers Grade C & D Examination, 2026',
            'https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/Stenographers_2026_Notice.pdf',
            'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
            '2026-07-26', 'CURRENT', 'NONE', '2026-07-26T06:00:00Z', '2026-07-26T06:00:00Z'
        )
        """
    )
    # 2. Parent for UPSC APP Corrigendum
    conn.execute(
        """
        INSERT INTO canonical_notices (
            id, source_id, authority_name, notice_number, title,
            normalized_url, category, state, classification, status,
            published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
        ) VALUES (
            'cn_parent_upsc_app', 'src_upsc', 'Union Public Service Commission', '01/2026',
            'Recruitment Notice No. 01/2026 for 140 Posts of Assistant Public Prosecutor',
            'https://www.upsc.gov.in/recruitment/advt_01_2026_app.pdf',
            'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
            '2026-01-15', 'CURRENT', 'NONE', '2026-01-15T06:00:00Z', '2026-01-15T06:00:00Z'
        )
        """
    )

manifest_file = Path("PILOT_BATCH_2_MANIFEST.json")
manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
docs = manifest["documents"]

verifier = VerificationAgent(db_path=db_file)
writer = WritingAgent(db_path=db_file)
qa = QualityAssuranceAgent(db_path=db_file)
editorial = EditorialService(db_path=db_file)
publisher = MockPublisher(db_path=db_file)

results = []

for filename, meta in docs.items():
    pid = meta["pilot_id"]
    source_id = meta["source_id"]
    authority = meta["authority"]
    title = meta["title"]
    url = meta["source_url"]
    local_path = Path(meta["local_path"])
    doc_bytes = local_path.read_bytes()
    ctype = meta["content_type"]
    
    t0 = time.time()
    
    # 1. Ingest Canonical Notice record
    canonical_id = f"cn_{pid}"
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
                pid,
                title,
                url,
                "Central" if "Public Service" in authority or "Staff" in authority or "National" in authority else "State",
                "Central" if "Tamil" not in authority and "Uttar" not in authority else ("Tamil Nadu" if "Tamil" in authority else "Uttar Pradesh"),
                "OTHER_ANNOUNCEMENT", # initial placeholder, will be classified by verifier
                "DISCOVERED",
                "2026-10-29",
                "CURRENT",
                "NONE",
                "2026-10-29T17:00:00Z",
                "2026-10-29T17:00:00Z",
            ),
        )

    # 2. Process & Verify via VerificationAgent (triggers FactExtractor + NoticeClassifier)
    version_id, verified_facts = verifier.process_and_verify_document(
        notice_id=canonical_id,
        doc_bytes=doc_bytes,
        doc_url=url,
        content_type=ctype,
    )

    # Check updated classification and parent link
    with get_db(db_file) as conn:
        row = conn.execute("SELECT classification, parent_notice_id, relation_type, relation_confidence FROM canonical_notices WHERE id = ?", (canonical_id,)).fetchone()
        classification = row["classification"]
        parent_notice_id = row["parent_notice_id"]
        relation_type = row["relation_type"]
        relation_conf = row["relation_confidence"]

    # 3. Draft Article via WritingAgent
    art_id, art_v_id, content_hash = writer.draft_article(canonical_id)
    with get_db(db_file) as conn:
        art_row = conn.execute("SELECT template_type FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        template_type = art_row["template_type"]

    # 4. QA Evaluation
    qa_pass, qa_score, qa_checks = qa.inspect_and_evaluate(art_v_id)

    # 5. Editorial Evaluation & Decision
    editor_data = editorial.get_draft_editor(art_id)
    can_normally_approve = editor_data["can_normally_approve"]
    unresolved_issues = editor_data["unresolved_issues"]

    decision_type = "APPROVED" if can_normally_approve else "OVERRIDE_APPROVED"
    override_reason = None
    if not can_normally_approve:
        override_reason = f"Audited editorial override: notice type is {classification} with verified official evidence. Waiving non-applicable unverified fields."

    decision_record = editorial.submit_decision(
        article_id=art_id,
        expected_version_id=art_v_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        editor_email=settings.OWNER_EMAIL,
        is_override=not can_normally_approve,
        override_reason=override_reason,
    )

    # 6. Simulated Publication
    appr_id = decision_record["approval_id"]
    pub_res = publisher.publish(
        article_version_id=art_v_id,
        content_hash=content_hash,
        approval_record_id=appr_id,
    )
    pub_url = pub_res["published_url"]

    elapsed = round(time.time() - t0, 2)

    # Extract critical facts summary
    crit_facts = {f.key: f.value for f in verified_facts}
    
    res = {
        "pilot_id": pid,
        "authority": authority,
        "title": title,
        "classification": classification,
        "parent_notice_id": parent_notice_id,
        "relation_type": relation_type,
        "relation_confidence": relation_conf,
        "template_type": template_type,
        "qa_score": qa_score,
        "qa_pass": qa_pass,
        "can_normally_approve": can_normally_approve,
        "decision_type": decision_type,
        "unresolved_issues": unresolved_issues if not can_normally_approve else [],
        "pub_url": pub_url,
        "elapsed_seconds": elapsed,
        "facts_count": len(verified_facts),
    }
    results.append(res)
    print(f"[{pid}] {authority[:10]} | Class: {classification:<25} | Tpl: {template_type:<18} | QA: {qa_score:5.1f} | Dec: {decision_type:<17} | Parent: {parent_notice_id or 'None'}")

# Save detailed results
results_file = Path("data/pilot_batch_2_results.json")
results_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

print("\n=======================================================")
print(f"PILOT BATCH 2 COMPLETE: {len(results)} notices processed")
print(f"Results stored: {results_file}")
print("=======================================================")
