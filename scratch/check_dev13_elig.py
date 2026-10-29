from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

pdf_ext = PdfDocumentExtractor()
b = open('data/development_notices/dev_13_tnpsc_special_competitive_exam.pdf', 'rb').read()
_, pages, _ = pdf_ext.extract(b)
facts = FactExtractor.extract_from_pages(pages, 'Tamil Nadu Public Service Commission', 'dev_13', 'url')
for f in facts:
    if f.key == 'eligibility':
        print(f"Key: {f.key} | Val: {f.value!r} | Page: {f.page_number} | Ev: {f.evidence_text[:80]!r}")
