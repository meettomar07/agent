import pymupdf
from testkart_intelligence.extraction.table_extractor import TableExtractor
import csv

# Read ground truth for new_val_10 and new_val_16
with open('NEW_DATASET_ACCURACY_EVALUATION.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        notice = row.get('Notice', '')
        if 'new_val_10' in notice or 'new_val_16' in notice:
            field = row.get('Field', '')
            gt = row.get('Ground_Truth', '')
            pred = row.get('Predicted', '')
            status = row.get('Status', '')
            if field == 'total_vacancies':
                print(f"{notice}: GT={gt!r} PRED={pred!r} STATUS={status}")

print()
print("--- Page 2 tables in new_val_10 ---")
doc = pymupdf.open('data/new_validation_notices/new_val_10_tnpsc_combined_accounts_services_exa.pdf')
page = doc[1]  # page 2
tabs = page.find_tables()
for t in tabs.tables:
    rows = t.extract()
    print("Table rows:")
    for r in rows:
        print(f"  {r}")
    print()

print()
print("--- Page 2 tables in new_val_16 ---")
doc2 = pymupdf.open('data/new_validation_notices/new_val_16_tnpsc_research_assistant_in_the_inst.pdf')
page2 = doc2[1]  # page 2
tabs2 = page2.find_tables()
for t in tabs2.tables:
    rows = t.extract()
    print("Table rows:")
    for r in rows:
        print(f"  {r}")
    print()
