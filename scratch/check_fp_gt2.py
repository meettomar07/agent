import csv
with open('NEW_DATASET_ACCURACY_EVALUATION.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

for row in rows:
    fname = row.get('notice_file', '')
    field = row.get('field_name', '')
    if any(n in fname for n in ['new_val_03', 'new_val_04', 'new_val_09', 'new_val_10', 'new_val_16', 'new_val_51']):
        if field == 'total_vacancies':
            print(f"{fname}: GT={row.get('ground_truth_value','')!r} PRED={row.get('extracted_value','')!r} STATUS={row.get('match_status','')}")
