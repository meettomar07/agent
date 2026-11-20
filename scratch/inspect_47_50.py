from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from pathlib import Path

pdf_ext = PdfDocumentExtractor()

for fname in ["new_val_47_ssc_important_notice___schedule_of.pdf", "new_val_50_ssc_important_notice__grade__c__st.pdf"]:
    p = Path("data/new_validation_notices") / fname
    data = p.read_bytes()
    text, pages, cnt = pdf_ext.extract(data)
    print(f"=== {fname} ===")
    print(f"Pages: {cnt}, text len: {len(text)}")
    print("First 500 chars:", repr(text[:500]))
    facts = FactExtractor.extract_from_pages(pages, "Staff Selection Commission", fname, "http://test")
    exam_facts = [f for f in facts if f.key == "exam_date"]
    print("Exam facts:", [(f.value, f.evidence_text[:60], f.confidence) for f in exam_facts])
