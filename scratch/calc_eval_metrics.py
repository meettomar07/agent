import json
from collections import defaultdict, Counter
from pathlib import Path

with open("data/independent_accuracy_audit_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

print(f"Loaded {len(results)} audit records.")

# 1. Classification Evaluation
classes = sorted(list({r["ground_truth"]["notice_type"] for r in results} | {r["prediction"]["classification"] for r in results}))
print("\n=== 1. CLASSIFICATION EVALUATION ===")
print("Classes present:", classes)

confusion_matrix = defaultdict(lambda: defaultdict(int))
for r in results:
    gt_c = r["ground_truth"]["notice_type"]
    pred_c = r["prediction"]["classification"]
    confusion_matrix[gt_c][pred_c] += 1

print("\nConfusion Matrix (Rows: Ground Truth, Cols: Prediction):")
header = f"{'Ground Truth':<30} | " + " | ".join(f"{c[:12]:<12}" for c in classes)
print(header)
print("-" * len(header))
for gt_c in classes:
    row_str = f"{gt_c:<30} | "
    for pred_c in classes:
        cnt = confusion_matrix[gt_c][pred_c]
        row_str += f"{cnt:<12} | "
    print(row_str)

# Per-class metrics
print("\nPer-class Metrics:")
print(f"{'Class':<30} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'Precision':<9} | {'Recall':<9} | {'F1':<9}")
print("-" * 80)
total_tp, total_fp, total_fn = 0, 0, 0
for c in classes:
    tp = confusion_matrix[c][c]
    fn = sum(confusion_matrix[c][p] for p in classes if p != c)
    fp = sum(confusion_matrix[g][c] for g in classes if g != c)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    total_tp += tp
    total_fp += fp
    total_fn += fn
    print(f"{c:<30} | {tp:<4} | {fp:<4} | {fn:<4} | {prec:9.2%} | {rec:9.2%} | {f1:9.2%}")

overall_acc = total_tp / len(results)
print(f"\nOverall Classification Accuracy: {total_tp}/{len(results)} ({overall_acc:.2%})")

# 2. Parent-Notice Linking Evaluation
print("\n=== 2. PARENT NOTICE LINKING EVALUATION ===")
# GT child notices: notices where is_child_notice is True
# True link: parent_notice_number matches expected parent
link_tp = 0 # correctly linked to expected parent
link_tn = 0 # correctly unlinked when not a child notice
link_fp = 0 # linked when should not be, or linked to wrong parent
link_fn = 0 # child notice failed to link (left as None)
ambiguous_count = 0

for r in results:
    gt_is_child = r["ground_truth"]["is_child_notice"]
    gt_parent = r["ground_truth"]["parent_notice_number"]
    pred_parent = r["prediction"]["parent_notice_id"]
    triage = r["prediction"]["triage_flag"]
    aid = r["audit_id"]
    
    if "AMBIGUOUS" in str(triage):
        ambiguous_count += 1
        
    if gt_is_child:
        if pred_parent:
            # Check if correct parent
            # e.g. ssc_je links to cn_parent_ssc_je; upsc_app links to cn_parent_upsc_app; uppsc_combined links to cn_parent_uppsc_combined_state
            if (aid == "audit_02" and "ssc_je" in pred_parent) or \
               (aid == "audit_05" and "upsc_app" in pred_parent) or \
               (aid == "audit_12" and "uppsc_combined_state" in pred_parent):
                link_tp += 1
                print(f"[{aid}] TP Link: correctly linked to {pred_parent}")
            else:
                link_fp += 1
                print(f"[{aid}] FP Link: linked to wrong parent {pred_parent} (expected {gt_parent})")
        else:
            link_fn += 1
            print(f"[{aid}] FN Link: child notice remained unlinked (expected {gt_parent})")
    else:
        if pred_parent:
            # Should have remained unlinked!
            link_fp += 1
            print(f"[{aid}] FP Link: standalone notice incorrectly linked to {pred_parent}")
        else:
            link_tn += 1

print(f"\nLinking Results: TP={link_tp}, TN={link_tn}, FP={link_fp}, FN={link_fn}, Ambiguous Flagged={ambiguous_count}")
link_prec = link_tp / (link_tp + link_fp) if (link_tp + link_fp) > 0 else 0.0
link_rec = link_tp / (link_tp + link_fn) if (link_tp + link_fn) > 0 else 0.0
link_f1 = 2 * link_prec * link_rec / (link_prec + link_rec) if (link_prec + link_rec) > 0 else 0.0
print(f"Linking Precision: {link_prec:.2%}")
print(f"Linking Recall:    {link_rec:.2%}")
print(f"Linking F1:        {link_f1:.2%}")
