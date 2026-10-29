from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.discovery.fetcher import SafeFetcher

fetcher = SafeFetcher()
content, ctype, final_url, _ = fetcher.fetch('https://nta.ac.in/Download/Notice/Notice_20250514161031.pdf')

verifier = VerificationAgent()
v_id, facts = verifier.process_and_verify_document(
    notice_id='not_9b1eef28c437',
    doc_bytes=content,
    doc_url=final_url,
    content_type=ctype,
)
print("Processed! Version ID:", v_id)
print("Extracted facts:")
for f in facts:
    print(f"  Key: {f.key}, Value: {f.value}, Status: {f.status}, Evidence: {f.evidence_text[:80] if f.evidence_text else None}")
