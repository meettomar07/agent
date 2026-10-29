import csv
with open('NEW_DATASET_ACCURACY_EVALUATION.csv', 'r', encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    for row in r:
        if row['field_name'] == 'total_vacancies':
            print(f"{row['notice_file']}: GT={row['ground_truth_value']!r} Pred={row['extracted_value']!r} Status={row['match_status']!r}")
