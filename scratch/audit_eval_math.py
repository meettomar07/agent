"""Comprehensive Audit of PRE_PRODUCTION_ACCURACY_EVALUATION.csv."""

import csv
from collections import defaultdict
import re

with open("PRE_PRODUCTION_ACCURACY_EVALUATION.csv", "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"Total rows: {len(rows)}")
unique_files = sorted(list(set(r["notice_file"] for r in rows)))
print(f"Unique files: {len(unique_files)}")
fields = sorted(list(set(r["field_name"] for r in rows)))
print(f"Unique fields: {len(fields)}")

# Audit math:
# For each field:
# Total evaluated = 33
# Support (ground truth applicable) = count where GT != 'N/A'
# Not applicable = count where GT == 'N/A'
# TP = count where GT != 'N/A' and EXT matches GT
# FP = count where EXT != 'N/A' and (GT == 'N/A' or EXT != GT)
# FN = count where GT != 'N/A' and (EXT == 'N/A' or EXT != GT)
# TN = count where GT == 'N/A' and EXT == 'N/A'
# Precision = TP / (TP + FP)
# Recall = TP / (TP + FN) = TP / Support
# Omission Accuracy = TN / (TN + FP_from_NA) = TN / Not_Applicable

audit_table = []
for f in fields:
    f_rows = [r for r in rows if r["field_name"] == f]
    support = sum(1 for r in f_rows if r["ground_truth_value"] != "N/A")
    not_app = sum(1 for r in f_rows if r["ground_truth_value"] == "N/A")
    
    tp = sum(1 for r in f_rows if r["match_status"] == "EXACT_MATCH")
    tn = sum(1 for r in f_rows if r["match_status"] == "NOT_APPLICABLE_IN_NOTICE")
    fn = sum(1 for r in f_rows if r["match_status"] in ("MISSING_IN_EXTRACTION", "PARTIAL_OR_DISCREPANCY"))
    fp = sum(1 for r in f_rows if r["match_status"] in ("SPURIOUS_EXTRACTION", "PARTIAL_OR_DISCREPANCY"))
    
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / support if support > 0 else 1.0
    omission = tn / not_app if not_app > 0 else 1.0
    
    audit_table.append({
        "field": f,
        "total": len(f_rows),
        "support": support,
        "not_applicable": not_app,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": prec,
        "recall": rec,
        "omission": omission,
    })

print("\n" + "=" * 90)
print(f"{'FIELD':<25} | {'SUP':<3} | {'N/A':<3} | {'TP':<3} | {'FP':<3} | {'FN':<3} | {'TN':<3} | {'PRECISION':<9} | {'RECALL':<8} | {'OMISSION':<8}")
print("=" * 90)
for a in audit_table:
    print(f"{a['field']:<25} | {a['support']:<3} | {a['not_applicable']:<3} | {a['tp']:<3} | {a['fp']:<3} | {a['fn']:<3} | {a['tn']:<3} | {a['precision']*100:8.1f}% | {a['recall']*100:7.1f}% | {a['omission']*100:7.1f}%")

print("-" * 90)
tot_sup = sum(a["support"] for a in audit_table)
tot_na = sum(a["not_applicable"] for a in audit_table)
tot_tp = sum(a["tp"] for a in audit_table)
tot_fp = sum(a["fp"] for a in audit_table)
tot_fn = sum(a["fn"] for a in audit_table)
tot_tn = sum(a["tn"] for a in audit_table)
tot_prec = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) > 0 else 0.0
tot_rec = tot_tp / tot_sup if tot_sup > 0 else 0.0
tot_om = tot_tn / tot_na if tot_na > 0 else 1.0

print(f"{'TOTAL':<25} | {tot_sup:<3} | {tot_na:<3} | {tot_tp:<3} | {tot_fp:<3} | {tot_fn:<3} | {tot_tn:<3} | {tot_prec*100:8.1f}% | {tot_rec*100:7.1f}% | {tot_om*100:7.1f}%")
print("=" * 90)
