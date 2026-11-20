from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.table_extractor import TableExtractor
from pathlib import Path

pdf_ext = PdfDocumentExtractor()
data = Path('data/new_validation_notices/new_val_51_ssc_tentative_vacancy_of_combined.pdf').read_bytes()
text, pages, cnt = pdf_ext.extract(data)
doc_tables = pages[0].get("document_tables", [])
print(f"Total doc_tables: {len(doc_tables)}")
for i, t in enumerate(doc_tables):
    print(f"Table {i} (p.{t.get('page_number')}): rows={len(t.get('rows', []))}")
    for r in t.get("rows", []):
        if any("total" in cell.lower() for cell in r):
            print("  TOTAL ROW:", r)

tbl_res = TableExtractor.parse_tables(doc_tables)
print("tbl_res.total_vacancies:", tbl_res.total_vacancies)
print("tbl_res.total_vacancies_evidence:", tbl_res.total_vacancies_evidence)
