import pymupdf
from testkart_intelligence.extraction.table_extractor import TableExtractor

doc = pymupdf.open('data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf')
tables = TableExtractor.extract_tables_from_doc(doc)
for t in tables:
    header_str = " | ".join(t["header"]).lower()
    if any(k in header_str for k in ("maximum age", "minimum age", "age limit", "age concession")):
        print(f"Table on page {t['page_number']}:")
        print("Header:", t["header"])
        for r in t["rows"][:8]:
            print("  ", r)
        break
