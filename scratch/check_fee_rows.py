import csv

with open("PRE_PRODUCTION_ACCURACY_EVALUATION.csv", "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

fee_rows = [r for r in rows if r["field_name"] == "application_fee"]
print(f"Fee rows total: {len(fee_rows)}")
for r in fee_rows:
    if r["ground_truth_value"] != "N/A" or r["extracted_value"] != "N/A":
        gt = r["ground_truth_value"].encode("ascii", errors="replace").decode("ascii")
        ext = r["extracted_value"].encode("ascii", errors="replace").decode("ascii")
        print(f"  {r['notice_file']:45s} | GT: {gt[:30]:30s} | EXT: {ext[:30]:30s} | {r['match_status']}")
