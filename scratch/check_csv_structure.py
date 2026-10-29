import csv
with open('NEW_DATASET_ACCURACY_EVALUATION.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    print("Columns:", list(rows[0].keys()))
    for row in rows:
        notice = row.get('notice_id', row.get('Notice', row.get('notice', '')))
        # Print all columns for first row to understand structure
        break

print()
print("First row keys and values:")
for k, v in rows[0].items():
    print(f"  {k!r}: {v!r}")
