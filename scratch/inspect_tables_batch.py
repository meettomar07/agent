from pathlib import Path
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor

pdf_ext = PdfDocumentExtractor()

for idx in [1, 2, 3, 4, 5, 9, 10, 11, 12, 13]:
    fname = f"new_val_{idx:02d}_"
    matches = list(Path("data/new_validation_notices").glob(f"{fname}*.pdf"))
    if not matches:
        continue
    fpath = matches[0]
    full_text, pages, count = pdf_ext.extract(fpath.read_bytes())
    doc_tables = pages[0].get("document_tables", [])
    print(f"\n=================== {fpath.name} (Tables: {len(doc_tables)}) ===================")
    for t in doc_tables:
        header_str = " | ".join(t["header"]).lower()
        # Check if table is exam scheme / marks table
        is_marks_tbl = any(k in header_str for k in ("mark", "scheme of exam", "qualifying"))
        if is_marks_tbl:
            print(f"  Page {t['page_number']} [MARKS TABLE]: {header_str[:80]}")
        elif any(k in header_str for k in ("vacanc", "post", "distribution")):
            print(f"  Page {t['page_number']} [VACANCY TABLE]: {header_str[:80]}")
            for r in t["rows"][-3:]:
                print(f"     Row: {' | '.join(r)[:100]}")
        elif any(k in header_str for k in ("notification", "schedule", "important date", "application")):
            print(f"  Page {t['page_number']} [SCHEDULE TABLE]: {header_str[:80]}")
            for r in t["rows"][:5]:
                print(f"     Row: {' | '.join(r)[:100]}")
