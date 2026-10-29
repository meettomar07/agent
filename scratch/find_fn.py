import csv
with open('NEW_DATASET_ACCURACY_EVALUATION.csv', 'r', encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    for row in r:
        if row['field_name'] == 'total_vacancies' and row['match_status'] == 'MISSING_EXTRACTION':
            print(f"File: {row['notice_file']} | GT: {row['ground_truth_value']}")
