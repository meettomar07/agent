import csv
from collections import defaultdict

with open("NEW_DATASET_ACCURACY_EVALUATION.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"Total rows in CSV: {len(rows)}")
fields = sorted(list(set(r["field_name"] for r in rows)))

stats = defaultdict(lambda: {
    "EXACT_MATCH": 0,
    "PARTIAL_OR_DISCREPANCY": 0,
    "MISSING_IN_EXTRACTION": 0,
    "SPURIOUS_EXTRACTION": 0,
    "NOT_APPLICABLE_IN_NOTICE": 0
})

for r in rows:
    stats[r["field_name"]][r["match_status"]] += 1

print("\n" + "="*80)
print(f"{'Field':<25} | {'Exact(TP)':<10} | {'Discrep(FP/FN)':<15} | {'Missing(FN)':<12} | {'Spurious(FP)':<12} | {'NotApp(TN)':<10}")
print("="*80)

for fld in fields:
    s = stats[fld]
    print(f"{fld:<25} | {s['EXACT_MATCH']:<10} | {s['PARTIAL_OR_DISCREPANCY']:<15} | {s['MISSING_IN_EXTRACTION']:<12} | {s['SPURIOUS_EXTRACTION']:<12} | {s['NOT_APPLICABLE_IN_NOTICE']:<10}")

print("="*80)

# How were metrics calculated in evaluate_new_52_dataset.py?
# In evaluate_new_52_dataset.py:
# EXACT_MATCH: tp += 1
# SPURIOUS_EXTRACTION: fp += 1, spurious_fp += 1
# MISSING_IN_EXTRACTION: fn += 1
# NOT_APPLICABLE: tn += 1
# PARTIAL_OR_DISCREPANCY: fp += 1, fn += 1, discrepancy_fp += 1

print("\nRecalculated Metrics (Standard definition where Discrepancy counts as FP and FN):")
print(f"{'Field':<25} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'TN':<4} | {'Precision':<9} | {'Recall':<8} | {'F1':<8}")
print("-" * 80)

total_tp = total_fp = total_fn = total_tn = 0
for fld in fields:
    s = stats[fld]
    tp = s["EXACT_MATCH"]
    fp = s["SPURIOUS_EXTRACTION"] + s["PARTIAL_OR_DISCREPANCY"]
    fn = s["MISSING_IN_EXTRACTION"] + s["PARTIAL_OR_DISCREPANCY"]
    tn = s["NOT_APPLICABLE_IN_NOTICE"]
    
    total_tp += tp
    total_fp += fp
    total_fn += fn
    total_tn += tn
    
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
    print(f"{fld:<25} | {tp:<4} | {fp:<4} | {fn:<4} | {tn:<4} | {p:<9.1%} | {r:<8.1%} | {f1:<8.1%}")

print("-" * 80)
overall_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
overall_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
overall_f1 = (2 * overall_p * overall_r) / (overall_p + overall_r) if (overall_p + overall_r) > 0 else 0.0
print(f"{'OVERALL (Micro-avg)':<25} | {total_tp:<4} | {total_fp:<4} | {total_fn:<4} | {total_tn:<4} | {overall_p:<9.1%} | {overall_r:<8.1%} | {overall_f1:<8.1%}")

# Macro-averages across fields:
precisions = []
recalls = []
f1s = []
for fld in fields:
    s = stats[fld]
    tp = s["EXACT_MATCH"]
    fp = s["SPURIOUS_EXTRACTION"] + s["PARTIAL_OR_DISCREPANCY"]
    fn = s["MISSING_IN_EXTRACTION"] + s["PARTIAL_OR_DISCREPANCY"]
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
    precisions.append(p)
    recalls.append(r)
    f1s.append(f1)

macro_p = sum(precisions) / len(precisions)
macro_r = sum(recalls) / len(recalls)
macro_f1 = sum(f1s) / len(f1s)
print(f"{'OVERALL (Macro-avg)':<25} | {'-':<4} | {'-':<4} | {'-':<4} | {'-':<4} | {macro_p:<9.1%} | {macro_r:<8.1%} | {macro_f1:<8.1%}")
