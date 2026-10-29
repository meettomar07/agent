import json
from pathlib import Path
import fitz
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "d:/Agent")

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

pdf_ext = PdfDocumentExtractor()

with open('GENERALIZATION_SET_MANIFEST.json', encoding='utf-8') as f:
    manifest = json.load(f)

exam_notices = []
for fname, meta in manifest['documents'].items():
    gt = meta.get('ground_truth_facts', {})
    ed = gt.get('exam_date')
    if ed and ed != 'N/A':
        exam_notices.append((fname, ed, meta))

notices_dir = Path("data/generalization_notices")

print(f"=== DETAILED EXAM DATE FAILURE AUDIT ({len(exam_notices)} NOTICES) ===")

for fname, ed, meta in exam_notices:
    fpath = notices_dir / fname
    doc = fitz.open(fpath)
    
    # 1. Run standard extraction
    full_text, pages, count = pdf_ext.extract(fpath.read_bytes())
    facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name=meta.get("authority", "Tamil Nadu Public Service Commission"),
        notice_title=fname,
        official_url=f"https://tnpsc.gov.in/{fname}"
    )
    ext_exam_date = next((f.value for f in facts if f.key == "exam_date"), "MISSING / NOT EXTRACTED")
    
    # 2. Search for the expected date in pages
    found_pages = []
    snippets = []
    for pidx, page in enumerate(doc):
        text = page.get_text()
        if ed in text or ed.replace(".", "/") in text or ed.replace(".", "-") in text:
            found_pages.append(pidx + 1)
            # Find snippet around the date
            pos = text.find(ed)
            if pos != -1:
                start = max(0, pos - 150)
                end = min(len(text), pos + 150)
                snippets.append((pidx + 1, text[start:end]))
                
    print("\n" + "=" * 80)
    print(f"Notice: {fname}")
    print(f"Expected Exam Date: {ed}")
    print(f"Machine Extracted  : {ext_exam_date}")
    print(f"Source Page(s)     : {found_pages}")
    print("Relevant Text Snippets:")
    for pno, snip in snippets[:2]:
        clean_snip = " ".join(snip.split())
        print(f"  [Page {pno}]: ... {clean_snip} ...")
