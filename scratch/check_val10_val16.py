import pymupdf
from testkart_intelligence.extraction.table_extractor import TableExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

for fname, label in [
    ('data/new_validation_notices/new_val_10_tnpsc_combined_accounts_services_exa.pdf', 'new_val_10'),
    ('data/new_validation_notices/new_val_16_tnpsc_research_assistant_in_the_inst.pdf', 'new_val_16'),
]:
    print(f"\n{'='*60}")
    print(f"FILE: {label}")
    doc = pymupdf.open(fname)
    tables = TableExtractor.extract_tables_from_doc(doc)
    result = TableExtractor.parse_tables(tables)
    print(f"  total_vacancies: {result.total_vacancies}")
    print(f"  evidence: {result.total_vacancies_evidence}")
    print(f"  post_vacancies count: {len(result.post_vacancies)}")
    for pv in result.post_vacancies:
        print(f"    - {pv.post_name}: {pv.vacancies} (page {pv.page_number})")
    
    # Also show which tables are detected as marks vs non-marks
    print(f"\n  Tables breakdown ({len(tables)} total):")
    for t in tables:
        is_marks = TableExtractor._is_marks_or_exam_scheme_table(t)
        header_str = ' | '.join(t['header'])[:80]
        print(f"    Page {t['page_number']}, Table {t['table_index']}: is_marks={is_marks} | header: {header_str}")
