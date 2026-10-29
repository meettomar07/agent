import json
from pathlib import Path
import re
import pymupdf

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()

new_val_dir = Path("data/new_validation_notices")
files = sorted(list(new_val_dir.glob("*")))

print(f"Analyzing {len(files)} new validation notices...")

doc_summaries = []

for i, p in enumerate(files):
    fname = p.name
    content = p.read_bytes()
    is_pdf = fname.endswith(".pdf")
    
    # Extract text
    if is_pdf:
        full_text, pages, page_count = pdf_ext.extract(content)
        is_scanned = any(pg.get("is_scanned") for pg in pages)
    else:
        text_str = content.decode("utf-8", errors="replace")
        full_text, pages, page_count = html_ext.extract(text_str)
        is_scanned = False
        
    chars = len(full_text)
    
    # Identify authority
    auth = "Unknown"
    if "_tnpsc_" in fname:
        auth = "Tamil Nadu Public Service Commission"
    elif "_nta_" in fname:
        auth = "National Testing Agency"
    elif "_upsc_" in fname:
        auth = "Union Public Service Commission"
    elif "_uppsc_" in fname:
        auth = "Uttar Pradesh Public Service Commission"
    elif "_ssc_" in fname:
        auth = "Staff Selection Commission"
        
    # Extract raw facts
    extracted_facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name=auth,
        notice_title=fname,
        official_url=f"https://official.gov.in/{fname}",
    )
    fact_dict = {f.key: f.value for f in extracted_facts}
    
    doc_summaries.append({
        "file_name": fname,
        "authority": auth,
        "format": "PDF" if is_pdf else "HTML",
        "page_count": page_count,
        "chars": chars,
        "is_scanned": is_scanned,
        "extracted_facts": fact_dict,
        "text_preview": full_text[:400].replace("\n", " "),
    })

print(f"\nProcessed {len(doc_summaries)} notices.")
scanned_count = sum(1 for d in doc_summaries if d["is_scanned"])
print(f"Scanned notices (processed via local OCR): {scanned_count}")
print(f"Text PDFs / HTML: {len(doc_summaries) - scanned_count}")

with open("scratch/new_dataset_extracted_raw.json", "w", encoding="utf-8") as f:
    json.dump(doc_summaries, f, indent=2)
