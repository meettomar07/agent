import csv
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('PRE_PRODUCTION_ACCURACY_EVALUATION.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        field = r['field_name']
        gt = r['ground_truth_value']
        ext = r['extracted_value']
        match = r['match_status']
        if gt != 'N/A' or ext != 'N/A':
            if match != 'EXACT_MATCH':
                print(f"[{field}] {r['notice_file']}: GT='{gt}' | EXT='{ext}' | {match}")
