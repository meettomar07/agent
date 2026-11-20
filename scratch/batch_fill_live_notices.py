import sqlite3
from testkart_intelligence.discovery.fetcher import SafeFetcher
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

# Get live notices needing document ingestion
rows = conn.execute(
    """
    SELECT cn.id, cn.authority_name, cn.title, cn.normalized_url
    FROM canonical_notices cn
    LEFT JOIN notice_versions nv ON cn.id = nv.notice_id
    WHERE nv.id IS NULL AND cn.normalized_url LIKE '%.pdf'
    ORDER BY cn.first_discovered_at DESC
    LIMIT 20
    """
).fetchall()

print(f"Found {len(rows)} live PDF notices pending ingestion.")
fetcher = SafeFetcher()
verifier = VerificationAgent()

ingested_count = 0
failed_count = 0

for r in rows:
    nid = r["id"]
    title = r["title"]
    url = r["normalized_url"]
    print(f"\nProcessing [{nid}]: {title[:50]}...")
    try:
        content_bytes, content_type, final_url, elapsed_ms = fetcher.fetch(url)
        v_id, facts = verifier.process_and_verify_document(
            notice_id=nid,
            doc_bytes=content_bytes,
            doc_url=final_url,
            content_type=content_type,
        )
        print(f"  -> SUCCESS: Version {v_id}, Extracted {len(facts)} facts (took {int(elapsed_ms)}ms)")
        ingested_count += 1
    except Exception as exc:
        print(f"  -> ERROR/SKIP: {exc}")
        failed_count += 1

print(f"\nBatch Ingestion Completed: {ingested_count} succeeded, {failed_count} skipped/failed.")
