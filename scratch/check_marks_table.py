import pymupdf
from testkart_intelligence.extraction.table_extractor import TableExtractor

doc = pymupdf.open('data/new_validation_notices/new_val_10_tnpsc_combined_accounts_services_exa.pdf')
tables = TableExtractor.extract_tables_from_doc(doc)
print(f'Total tables extracted: {len(tables)}')
for t in tables:
    is_marks = TableExtractor._is_marks_or_exam_scheme_table(t)
    rows_text = str(t['rows']).lower()
    if '510' in rows_text or 'maximum marks' in rows_text:
        print(f"Page {t['page_number']}: is_marks={is_marks}")
        print(f"  Header: {t['header']}")
        rows_sample = ' '.join(' '.join(str(c) for c in r) for r in t['rows'][:8]).lower()
        print(f"  Rows sample 0-7: {rows_sample[:400]}")
        print()

print("--- new_val_16 ---")
doc2 = pymupdf.open('data/new_validation_notices/new_val_16_tnpsc_research_assistant_in_the_inst.pdf')
tables2 = TableExtractor.extract_tables_from_doc(doc2)
print(f'Total tables extracted: {len(tables2)}')
for t in tables2:
    is_marks = TableExtractor._is_marks_or_exam_scheme_table(t)
    rows_text = str(t['rows']).lower()
    if '510' in rows_text or 'maximum marks' in rows_text:
        print(f"Page {t['page_number']}: is_marks={is_marks}")
        print(f"  Header: {t['header']}")
        rows_sample = ' '.join(' '.join(str(c) for c in r) for r in t['rows'][:8]).lower()
        print(f"  Rows sample 0-7: {rows_sample[:400]}")
        print()
