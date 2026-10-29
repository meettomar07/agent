import csv

with open('INDEPENDENT_GENERALIZATION_EVALUATION.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

for r in rows:
    if r['field_name'] in ('age_limit', 'eligibility') and r['match_status'] not in ('EXACT_MATCH', 'NOT_APPLICABLE_IN_NOTICE'):
        print(f"[{r['field_name']}] {r['notice_file']}:\n  GT : {r['ground_truth_value']}\n  EXT: {r['extracted_value']}\n  STATUS: {r['match_status']}\n")
