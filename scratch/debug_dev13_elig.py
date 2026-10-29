import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

pdf_ext = PdfDocumentExtractor()
fpath = Path("data/development_notices/dev_13_tnpsc_special_competitive_exam.pdf")
full_text, pages, count = pdf_ext.extract(fpath.read_bytes())
facts = FactExtractor.extract_from_pages(
    pages=pages,
    authority_name="Tamil Nadu Public Service Commission",
    notice_title="dev_13",
    official_url="https://tnpsc.gov.in/dev13.pdf"
)

for f in facts:
    if "eligibility" in f.key:
        print(f"Key: {f.key} | Value: {f.value} | Page: {f.page_number}")
        print(f"Evidence: {f.evidence_text}\n")
