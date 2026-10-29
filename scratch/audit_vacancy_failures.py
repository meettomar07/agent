import csv

with open("NEW_DATASET_ACCURACY_EVALUATION.csv", encoding="utf-8") as f:
    rows = [r for r in csv.DictReader(f) if r["field_name"] == "total_vacancies"]

print("="*100)
print("AUDIT OF VACANCY PREDICTIONS (52 NOTICES)")
print("="*100)

for r in rows:
    status = r["match_status"]
    if status == "NOT_APPLICABLE_IN_NOTICE":
        continue
    fname = r["notice_file"]
    auth = r["authority"]
    gt = r["ground_truth_value"]
    ext = r["extracted_value"]
    ev = r["evidence_quote"]
    pno = r["page_number"]
    print(f"\nFile: {fname} [{auth}]")
    print(f"  Status: {status} | Page: {pno}")
    print(f"  Ground Truth: {gt}")
    print(f"  Extracted:    {ext}")
    print(f"  Evidence:     {ev}")
