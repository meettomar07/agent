import csv

with open('NEW_DATASET_ACCURACY_EVALUATION.csv', 'r', encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    vac_rows = [row for row in r if row['field_name'] == 'total_vacancies']

print(f"Total vacancy evaluated rows: {len(vac_rows)}")
fps = [row for row in vac_rows if row['match_status'] in ('PARTIAL_OR_DISCREPANCY', 'SPURIOUS_EXTRACTION')]
fns = [row for row in vac_rows if row['match_status'] in ('PARTIAL_OR_DISCREPANCY', 'MISSING_EXTRACTION')]

print("\n--- FALSE POSITIVES / DISCREPANCIES (8 total) ---")
for row in fps:
    print(f"* File: {row['notice_file']}")
    print(f"  GT: {row['ground_truth_value']!r} | Extracted: {row['extracted_value']!r} | Page: {row['page_number']}")
    print(f"  Evidence: {row['evidence_quote']}")

print("\n--- PURE FALSE NEGATIVES / MISSING (6 total) ---")
for row in fns:
    if row['match_status'] == 'MISSING_EXTRACTION':
        print(f"* File: {row['notice_file']}")
        print(f"  GT: {row['ground_truth_value']!r} | Extracted: {row['extracted_value']!r}")
        print(f"  Evidence: {row['evidence_quote']}")
