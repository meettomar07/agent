from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.table_extractor import TableExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from pathlib import Path

pdf_ext = PdfDocumentExtractor()
data = Path('data/new_validation_notices/new_val_51_ssc_tentative_vacancy_of_combined.pdf').read_bytes()
text, pages, cnt = pdf_ext.extract(data)
tables = TableExtractor.extract_tables_from_doc(pages)
tbl_res = TableExtractor.parse_tables(tables, 'Staff Selection Commission')
print("tbl_res.total_vacancies:", tbl_res.total_vacancies)
print("tbl_res.total_vacancies_evidence:", tbl_res.total_vacancies_evidence)
for t in tables:
    for r in t["rows"]:
        if any("total" in cell.lower() for cell in r):
            print("TOTAL ROW on page", t["page_number"], ":", r)
