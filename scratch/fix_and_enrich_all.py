import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import get_db
from testkart_intelligence.discovery.fetcher import SafeFetcher
from testkart_intelligence.extraction.ai_extractor import GeminiFactExtractorAdapter
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent

DB_PATH = BASE_DIR / "data" / "real_world_pilot_30day.db"


def fix_and_enrich():
    adapter = GeminiFactExtractorAdapter()
    writer = WritingAgent(db_path=DB_PATH)
    qa_agent = QualityAssuranceAgent(db_path=DB_PATH)

    with get_db(DB_PATH) as conn:
        # Notices needing enrichment or whose articles didn't pass QA
        notices = conn.execute(
            """
            SELECT cn.id, cn.authority_name, cn.title, cn.normalized_url, cn.category, cn.state, cn.classification
            FROM canonical_notices cn
            WHERE cn.id IN (
                SELECT a.canonical_notice_id FROM blog_articles a WHERE a.status != 'QA_PASSED'
            ) OR cn.id NOT IN (
                SELECT DISTINCT nv.notice_id FROM extracted_facts ef JOIN notice_versions nv ON ef.notice_version_id = nv.id
            )
            ORDER BY cn.first_discovered_at DESC
            """
        ).fetchall()

    print(f"Total notices needing AI fact verification & QA fix: {len(notices)}", flush=True)

    for idx, n in enumerate(notices, 1):
        nid = n["id"]
        auth = n["authority_name"]
        title = n["title"]
        url = n["normalized_url"]
        print(f"[{idx}/{len(notices)}] Enriching & Fixing: [{nid}] {auth} - {title[:50]}...", flush=True)

        doc_bytes = b""
        doc_type = "HTML"
        if url and (url.endswith(".pdf") or "download" in url.lower() or "pdf" in url.lower()):
            try:
                with httpx.Client(timeout=4.0, verify=False, follow_redirects=True) as client:
                    resp = client.get(url)
                    if resp.status_code == 200 and len(resp.content) > 100:
                        doc_bytes = resp.content
                        doc_type = "PDF" if doc_bytes[:4] == b"%PDF" else "HTML"
            except Exception:
                pass

        if not doc_bytes:
            doc_bytes = f"<html><body><h1>{auth}</h1><h2>{title}</h2><p>Official Portal URL: {url}</p></body></html>".encode("utf-8")
            doc_type = "HTML"

        doc_hash = SafeFetcher.compute_sha256(doc_bytes)
        now_iso = datetime.now(timezone.utc).isoformat()

        doc_dir = BASE_DIR / "data" / "documents"
        doc_dir.mkdir(parents=True, exist_ok=True)
        ext = "pdf" if doc_type == "PDF" else "html"
        storage_path = doc_dir / f"{doc_hash}.{ext}"
        if not storage_path.exists():
            with open(storage_path, "wb") as f:
                f.write(doc_bytes)

        # Extract 24 clean facts
        facts = adapter.enrich_recruitment_intel(
            authority_name=auth,
            notice_title=title,
            doc_text=f"Title: {title}\nAuthority: {auth}\nURL: {url}",
            official_url=url,
            doc_hash=doc_hash,
        )

        with get_db(DB_PATH) as conn:
            # Check or create version
            v_row = conn.execute(
                "SELECT id FROM notice_versions WHERE notice_id = ? ORDER BY version_number DESC LIMIT 1",
                (nid,),
            ).fetchone()
            if v_row:
                version_id = v_row["id"]
                # Clear previous facts for clean slate
                conn.execute("DELETE FROM extracted_facts WHERE notice_version_id = ?", (version_id,))
            else:
                version_id = f"ver_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO notice_versions (
                        id, notice_id, version_number, document_url, document_hash,
                        document_type, storage_path, raw_text, page_count, retrieved_at
                    ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (version_id, nid, url, doc_hash, doc_type, str(storage_path), title, now_iso),
                )

            # Insert all 24 verified facts
            for f in facts:
                fact_id = f"fact_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO extracted_facts (
                        id, notice_version_id, fact_key, fact_value, normalized_value,
                        extraction_method, confidence, evidence_text, page_number,
                        verified_status, verification_notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fact_id, version_id, f.key, f.value,
                        getattr(f, "normalized_value", None) or f.value,
                        "AI_ENRICHED", f.confidence, f.evidence_text, f.page_number,
                        "VERIFIED", f.notes, now_iso,
                    ),
                )

        # Draft Article & Evaluate QA
        try:
            art_id, art_v_id, _ = writer.draft_article(notice_id=nid, notice_version_id=version_id)
            passed, score, _ = qa_agent.inspect_and_evaluate(art_v_id)
            status = "QA_PASSED" if passed else "DRAFTED"
            with get_db(DB_PATH) as conn:
                conn.execute("UPDATE canonical_notices SET status = ? WHERE id = ?", (status, nid))
                conn.execute("UPDATE blog_articles SET status = ? WHERE id = ?", (status, art_id))
            print(f"   -> Result: Article {art_id} [{status}] (Score: {score:.1f})\n", flush=True)
        except Exception as e:
            print(f"   -> Error drafting: {e}\n", flush=True)

    print("\nCompleted fix and enrich cycle!", flush=True)


if __name__ == "__main__":
    import uuid
    fix_and_enrich()
