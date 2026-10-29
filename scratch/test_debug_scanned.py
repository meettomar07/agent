import pymupdf
import uuid
from datetime import datetime, timezone
from testkart_intelligence.database.connection import get_db, init_db
from testkart_intelligence.extraction.verifier import VerificationAgent

doc = pymupdf.open()
doc.new_page()
pdf_bytes = doc.tobytes()
doc.close()

db_path = "data/test_debug.db"
init_db(db_path)

verifier = VerificationAgent(db_path=db_path)
notice_id = f"not_scan_{uuid.uuid4().hex[:8]}"
now_iso = datetime.now(timezone.utc).isoformat()

with get_db(db_path) as conn:
    conn.execute(
        """
        INSERT INTO canonical_notices (id, source_id, authority_name, notice_number, title,
            normalized_url, category, state, classification, status, first_discovered_at, last_updated_at)
        VALUES (?, 'src_upsc', 'Union Public Service Commission', '13-2025',
            'Scanned Notice 07', 'https://www.upsc.gov.in/scanned.pdf', 'Central', 'Central',
            'RECRUITMENT_NOTIFICATION', 'DISCOVERED', ?, ?)
        """,
        (notice_id, now_iso, now_iso),
    )

print("Calling process_and_verify_document...")
v_id, facts = verifier.process_and_verify_document(notice_id, pdf_bytes, "https://www.upsc.gov.in/scanned.pdf", "application/pdf")
print("Success! v_id:", v_id, "facts count:", len(facts))
