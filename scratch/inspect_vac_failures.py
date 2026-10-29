import csv

with open("NEW_DATASET_ACCURACY_EVALUATION.csv", "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

vac_rows = [r for r in rows if r["field_name"] == "total_vacancies"]
print(f"Total vacancy rows: {len(vac_rows)}")
for r in vac_rows:
    if r["match_status"] != "NOT_APPLICABLE_IN_NOTICE" and r["match_status"] != "EXACT_MATCH":
        print(f"Doc: {r['notice_file']} | Status: {r['match_status']} | GT: {r['ground_truth_value']} | Extracted: {r['extracted_value']} | Evidence: {r['evidence_quote']}")
