import csv
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("INDEPENDENT_GENERALIZATION_EVALUATION.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"Total evaluated rows: {len(rows)}")

# Print all discrepancies and misses
for r in rows:
    if r["match_status"] in ("PARTIAL_OR_DISCREPANCY", "SPURIOUS_EXTRACTION", "MISSING_IN_EXTRACTION"):
        print("-" * 80)
        print(f"File: {r['notice_file']} | Field: {r['field_name']} | Status: {r['match_status']}")
        print(f"  GT Expected : {r['ground_truth_value']}")
        print(f"  Extracted   : {r['extracted_value']}")
        print(f"  Confidence  : {r['confidence']}")
        print(f"  Evidence    : {r['evidence_text']}")
