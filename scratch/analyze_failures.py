import csv
from collections import defaultdict

with open("NEW_DATASET_ACCURACY_EVALUATION.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

target_fields = ['exam_date', 'total_vacancies', 'age_limit', 'eligibility']
failures = [r for r in rows if r['field_name'] in target_fields and r['match_status'] not in ('EXACT_MATCH', 'NOT_APPLICABLE_IN_NOTICE')]

print(f"Total failures across target fields: {len(failures)}")
by_field = defaultdict(list)
for r in failures:
    by_field[r['field_name']].append(r)

for fld, items in by_field.items():
    print(f"\n{'='*30} Field: {fld} ({len(items)} failures) {'='*30}")
    for it in items:
        print(f"File: {it['notice_file']} | Status: {it['match_status']}")
        print(f"  Expected:  {it['ground_truth_value']}")
        print(f"  Extracted: {it['extracted_value']}")
        print(f"  Evidence:  {it['evidence_quote'][:120]}")
