from pathlib import Path
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.table_extractor import TableExtractor

pdf_ext = PdfDocumentExtractor()
fpath = Path("data/new_validation_notices/new_val_01_tnpsc_combined_civil_services_examin.pdf")
full_text, pages, count = pdf_ext.extract(fpath.read_bytes())
doc_tables = pages[0].get("document_tables", [])
print(f"Total tables: {len(doc_tables)}")
for t in doc_tables:
    pno = t["page_number"]
    header = " | ".join(t["header"])
    rows_text = " // ".join(" | ".join(r) for r in t["rows"][:3])
    if any(k in header.lower() or k in rows_text.lower() for k in ["date", "exam", "paper", "04.01.2025"]):
        print(f"\nPage {pno} Table:")
        print(f"  Header: {header}")
        for r in t["rows"]:
            print(f"    {' | '.join(r)}")
