import csv

with open('FACT_EXTRACTION_EVALUATION.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

notices = {}
for r in rows:
    f_name = r['notice_file']
    if f_name not in notices:
        notices[f_name] = {
            'authority': r['authority'],
            'format': r['document_format'],
            'cat': r['notice_category'],
            'sha256': r['sha256'],
            'subset': r['evaluation_subset']
        }

print('Total evaluated notice documents:', len(notices))
for k, v in notices.items():
    print(f'{k}: {v["authority"]} | {v["format"]} | {v["cat"]} | {v["subset"]} | {v["sha256"][:12]}')

fields = set(r['field_name'] for r in rows)
print('\nField names evaluated:', fields)
