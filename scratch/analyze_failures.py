import csv

with open("PRE_PRODUCTION_ACCURACY_EVALUATION.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

spurious = [r for r in rows if r["match_status"] == "SPURIOUS_EXTRACTION"]
missing = [r for r in rows if r["match_status"] == "MISSING_IN_EXTRACTION"]
partial = [r for r in rows if r["match_status"] == "PARTIAL_OR_DISCREPANCY"]

print(f"Total rows: {len(rows)}")
print(f"SPURIOUS_EXTRACTION (FP on N/A): {len(spurious)}")
for r in spurious:
    print(f"  [SPURIOUS] Doc: {r['notice_file']} | Format: {r['document_format']} | Field: {r['field_name']} | Extracted: {r['extracted_value']} | GT: {r['ground_truth_value']}")

print(f"\nPARTIAL_OR_DISCREPANCY (FP & FN): {len(partial)}")
for r in partial:
    print(f"  [PARTIAL] Doc: {r['notice_file']} | Format: {r['document_format']} | Field: {r['field_name']} | Extracted: {r['extracted_value']} | GT: {r['ground_truth_value']}")

print(f"\nMISSING_IN_EXTRACTION (FN): {len(missing)}")
for r in missing:
    print(f"  [MISSING] Doc: {r['notice_file']} | Format: {r['document_format']} | Field: {r['field_name']} | Extracted: {r['extracted_value']} | GT: {r['ground_truth_value']}")
