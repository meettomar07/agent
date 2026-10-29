"""Test fact extraction on the 13 development notices."""

import json
from pathlib import Path
import pymupdf

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.table_extractor import TableExtractor

pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()

dev_dir = Path("data/development_notices")
with open("DEVELOPMENT_SET_MANIFEST.json", "r", encoding="utf-8") as f:
    dev_manifest = json.load(f)

print("=" * 80)
print(f"EVALUATING EXTRACTION ON DEVELOPMENT SET ({len(dev_manifest['documents'])} NOTICES)")
print("=" * 80)

for fname in sorted(dev_manifest["documents"].keys()):
    p = dev_dir / fname
    bytes_data = p.read_bytes()
    is_pdf = fname.endswith(".pdf")

    if is_pdf:
        full_text, pages, count = pdf_ext.extract(bytes_data)
    else:
        text_str = bytes_data.decode("utf-8", errors="replace")
        full_text, pages, count = html_ext.extract(text_str)

    authority = "Tamil Nadu Public Service Commission" if "tnpsc" in fname else ("Union Public Service Commission" if "upsc" in fname else ("Staff Selection Commission" if "ssc" in fname else "National Testing Agency"))

    facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name=authority,
        notice_title=fname,
        official_url=f"https://official.gov.in/{fname}",
    )
    fact_dict = {f.key: f.value for f in facts}

    print(f"\nNotice: {fname} (Pages: {count})")
    print(f"  * Notice Number : {fact_dict.get('notice_number', 'N/A')}")
    print(f"  * Vacancies     : {fact_dict.get('total_vacancies', 'N/A')}")
    print(f"  * App Start     : {fact_dict.get('application_start_date', 'N/A')}")
    print(f"  * App End       : {fact_dict.get('application_end_date', 'N/A')}")
    print(f"  * Exam Date     : {fact_dict.get('exam_date', 'N/A')}")
    print(f"  * Age Limit     : {fact_dict.get('age_limit', 'N/A')}")
    print(f"  * Eligibility   : {fact_dict.get('eligibility', 'N/A')[:60] if fact_dict.get('eligibility') else 'N/A'}")
    print(f"  * Fee           : {fact_dict.get('application_fee', 'N/A')}")
