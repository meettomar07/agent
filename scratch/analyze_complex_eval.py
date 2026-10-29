import csv
from collections import Counter

with open("COMPLEX_TABLE_ACCURACY_EVALUATION.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

fields = [
    "total_vacancies",
    "application_start_date",
    "application_end_date",
    "exam_date",
    "age_limit",
    "eligibility",
    "application_fee",
]

for field in ["total_vacancies", "eligibility", "age_limit", "exam_date"]:
    print(f"\n=================== {field.upper()} ===================")
    fps = [r for r in rows if r[f"{field}_status"] == "FP"]
    fns = [r for r in rows if r[f"{field}_status"] == "FN"]
    tps = [r for r in rows if r[f"{field}_status"] == "TP"]
    print(f"TP: {len(tps)} | FP: {len(fps)} | FN: {len(fns)}")
    print(f"\nFalse Positives (sample 5):")
    for r in fps[:5]:
        print(f"  File: {r['file']}")
        print(f"    GT:        {r[f'{field}_gt']}")
        print(f"    Extracted: {r[f'{field}_extracted']}")
    print(f"\nFalse Negatives (sample 5):")
    for r in fns[:5]:
        print(f"  File: {r['file']}")
        print(f"    GT:        {r[f'{field}_gt']}")
