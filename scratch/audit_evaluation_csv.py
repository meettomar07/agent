import csv

with open("PRE_PRODUCTION_ACCURACY_EVALUATION.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total rows in evaluation: {len(rows)}")

discrepancies = [r for r in rows if r["match_status"] not in ("EXACT_MATCH", "NOT_APPLICABLE_IN_NOTICE")]
print(f"Total discrepancies (FP, FN, Partial): {len(discrepancies)}\n")

for d in discrepancies:
    ext_s = d['extracted_value'].encode('ascii', errors='replace').decode('ascii')
    gt_s = d['ground_truth_value'].encode('ascii', errors='replace').decode('ascii')
    ev_s = d['evidence_quote'].encode('ascii', errors='replace').decode('ascii')
    print(f"[{d['match_status']}] {d['notice_file']} | Field: {d['field_name']}")
    print(f"   GT : {gt_s}")
    print(f"   EXT: {ext_s}")
    print(f"   EV : {ev_s}")
    print()
