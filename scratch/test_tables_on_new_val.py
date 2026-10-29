import json
from pathlib import Path
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.table_extractor import TableExtractor

pdf_ext = PdfDocumentExtractor()

test_files = [
    "new_val_01_tnpsc_combined_civil_services_examin.pdf",
    "new_val_02_tnpsc_assistant_public_prosecutor__g.pdf",
    "new_val_03_tnpsc_combined_technical_services_ex.pdf",
    "new_val_04_tnpsc_combined_technical_services_ex.pdf",
    "new_val_05_tnpsc_combined_civil_services_examin.pdf",
    "new_val_09_tnpsc_assistant_agricultural_officer.pdf",
    "new_val_10_tnpsc_combined_accounts_services_exa.pdf",
    "new_val_16_tnpsc_research_assistant_in_the_inst.pdf",
]

for fname in test_files:
    fpath = Path("data/new_validation_notices") / fname
    if not fpath.exists():
        continue
    full_text, pages, count = pdf_ext.extract(fpath.read_bytes())
    doc_tables = pages[0].get("document_tables", [])
    res = TableExtractor.parse_tables(doc_tables, "TNPSC")
    print(f"\n{fname} (tables found: {len(doc_tables)}):")
    print(f"  * Total Vacancies : {res.total_vacancies} (Page {res.total_vacancies_page})")
    print(f"  * Evidence        : {res.total_vacancies_evidence}")
    print(f"  * App Start       : {res.application_start_date}")
    print(f"  * App End         : {res.application_end_date}")
    print(f"  * Exam Date       : {res.exam_date}")
    print(f"  * Age Limit       : {res.age_limit}")
    print(f"  * Eligibility     : {res.eligibility[:70] if res.eligibility else None}")
