import httpx
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.database.connection import get_db

notice_id = "not_ad71f5a41396"

with get_db() as conn:
    notice = conn.execute("SELECT * FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()
    print("Notice:", notice["title"])
    url = notice["normalized_url"]

print(f"Fetching document from {url}...")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
with httpx.Client(timeout=30.0, verify=False) as client:
    resp = client.get(url, headers=headers)
    print("Status:", resp.status_code, "Bytes:", len(resp.content))

verifier = VerificationAgent()
version_id, facts = verifier.process_and_verify_document(
    notice_id=notice_id,
    doc_bytes=resp.content,
    doc_url=url,
    content_type="application/pdf"
)

print(f"Created version {version_id} with {len(facts)} facts!")
with get_db() as conn:
    n_after = conn.execute("SELECT * FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()
    print("Notice status after:", n_after["status"])
    print("Application end date:", n_after["application_end_date"])
    print("Published date:", n_after["published_date"])
    v_count = conn.execute("SELECT count(*) as c FROM notice_versions WHERE notice_id = ?", (notice_id,)).fetchone()["c"]
    f_count = conn.execute("SELECT count(*) as c FROM extracted_facts ef JOIN notice_versions nv ON ef.notice_version_id = nv.id WHERE nv.notice_id = ?", (notice_id,)).fetchone()["c"]
    print(f"Versions: {v_count}, Facts in DB: {f_count}")
