import csv
with open('NEW_DATASET_ACCURACY_EVALUATION.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        notice = row.get('Notice', '')
        if any(n in notice for n in ['new_val_03', 'new_val_04', 'new_val_09', 'new_val_10', 'new_val_16', 'new_val_51']):
            field = row.get('Field', '')
            if field == 'total_vacancies':
                print(f"{notice}: GT={row.get('Ground_Truth','')!r} PRED={row.get('Predicted','')!r} STATUS={row.get('Status','')}")
