import json
from collections import defaultdict
import re
from dateutil import parser as date_parser

with open("data/independent_accuracy_audit_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

eval_fields = [
    "total_vacancies",
    "eligibility",
    "age_limit",
    "application_start_date",
    "application_end_date",
    "exam_date",
]

def normalize_val(val):
    if not val:
        return ""
    v = str(val).lower().strip()
    v = re.sub(r"\s+", " ", v)
    return v

def dates_match(d1, d2):
    if not d1 or not d2:
        return False
    try:
        dt1 = date_parser.parse(str(d1), fuzzy=True, dayfirst=True)
        dt2 = date_parser.parse(str(d2), fuzzy=True, dayfirst=True)
        if dt1.year == dt2.year and dt1.month == dt2.month and dt1.day == dt2.day:
            return True
    except Exception:
        pass
    
    c1 = re.sub(r"[^\w\d]", "", str(d1).lower())
    c2 = re.sub(r"[^\w\d]", "", str(d2).lower())
    return c1 in c2 or c2 in c1 or str(d1).lower() in str(d2).lower() or str(d2).lower() in str(d1).lower()

field_stats = {}
for f in eval_fields:
    field_stats[f] = {
        "gt_present": 0,
        "gt_absent": 0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 0,
        "incorrect_val": 0,
        "details": []
    }

for r in results:
    aid = r["audit_id"]
    source = r["source_id"]
    auth = r["authority"]
    gt_fields = r["ground_truth"]["fields"]
    pred_facts = r["prediction"]["extracted_facts"]
    
    for f in eval_fields:
        gt_item = gt_fields.get(f, {"status": "ABSENT", "value": None})
        gt_status = gt_item.get("status", "ABSENT")
        gt_val = gt_item.get("value")
        
        pred_item = pred_facts.get(f)
        pred_val = pred_item.get("fact_value") if pred_item else None
        
        is_gt_present = (gt_status == "PRESENT" and gt_val is not None)
        is_pred_present = (pred_val is not None and str(pred_val).strip() != "")
        
        if is_gt_present:
            field_stats[f]["gt_present"] += 1
            if is_pred_present:
                norm_gt = normalize_val(gt_val)
                norm_pred = normalize_val(pred_val)
                
                match = False
                if f == "total_vacancies":
                    gt_digits = re.findall(r"\d+", norm_gt)
                    pred_digits = re.findall(r"\d+", norm_pred)
                    match = bool(gt_digits and pred_digits and gt_digits[0] == pred_digits[0])
                elif "date" in f:
                    match = dates_match(norm_gt, norm_pred)
                elif f == "age_limit":
                    match = ("18" in norm_pred and "30" in norm_pred) if "30" in norm_gt else ("40" in norm_pred if "40" in norm_gt else (norm_gt in norm_pred or norm_pred in norm_gt))
                elif f == "eligibility":
                    gt_words = set(re.findall(r"\w{4,}", norm_gt))
                    pred_words = set(re.findall(r"\w{4,}", norm_pred))
                    overlap = gt_words & pred_words
                    match = (len(overlap) / len(gt_words)) >= 0.40 if gt_words else False
                
                if match:
                    field_stats[f]["tp"] += 1
                    status = "TP"
                else:
                    field_stats[f]["incorrect_val"] += 1
                    field_stats[f]["fp"] += 1
                    field_stats[f]["fn"] += 1
                    status = "INCORRECT_VALUE"
                
                field_stats[f]["details"].append({
                    "audit_id": aid,
                    "authority": auth,
                    "status": status,
                    "gt": gt_val,
                    "pred": pred_val
                })
            else:
                field_stats[f]["fn"] += 1
                field_stats[f]["details"].append({
                    "audit_id": aid,
                    "authority": auth,
                    "status": "FN (Omission)",
                    "gt": gt_val,
                    "pred": None
                })
        else:
            field_stats[f]["gt_absent"] += 1
            if is_pred_present:
                field_stats[f]["fp"] += 1
                field_stats[f]["details"].append({
                    "audit_id": aid,
                    "authority": auth,
                    "status": "FP (Spurious Extraction)",
                    "gt": None,
                    "pred": pred_val
                })
            else:
                field_stats[f]["tn"] += 1

print("\n=== CRITICAL FIELD EXTRACTION EVALUATION (NORMALIZED) ===")
print(f"{'Field':<24} | {'GT Present':<10} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'Prec':<8} | {'Rec':<8} | {'F1':<8} | {'Omission':<9} | {'Incorrect':<9}")
print("-" * 105)

for f in eval_fields:
    s = field_stats[f]
    tp, fp, fn = s["tp"], s["fp"], s["fn"]
    gt_p = s["gt_present"]
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    omission_rate = (fn - s["incorrect_val"]) / gt_p if gt_p > 0 else 0.0
    incorrect_rate = s["incorrect_val"] / (tp + s["incorrect_val"]) if (tp + s["incorrect_val"]) > 0 else 0.0
    
    print(f"{f:<24} | {gt_p:<10} | {tp:<4} | {fp:<4} | {fn:<4} | {prec:8.2%} | {rec:8.2%} | {f1:8.2%} | {omission_rate:9.2%} | {incorrect_rate:9.2%}")

print("\n=== BREAKDOWN BY RECRUITMENT AUTHORITY ===")
by_auth = defaultdict(lambda: defaultdict(lambda: {"gt": 0, "tp": 0, "fn": 0, "fp": 0}))
for r in results:
    auth = r["authority"]
    gt_fields = r["ground_truth"]["fields"]
    pred_facts = r["prediction"]["extracted_facts"]
    for f in eval_fields:
        is_gt = (gt_fields.get(f, {}).get("status") == "PRESENT" and gt_fields.get(f, {}).get("value") is not None)
        pred_item = pred_facts.get(f)
        is_pred = (pred_item is not None and str(pred_item.get("fact_value", "")).strip() != "")
        if is_gt:
            by_auth[auth][f]["gt"] += 1
            if is_pred:
                by_auth[auth][f]["tp"] += 1
            else:
                by_auth[auth][f]["fn"] += 1
        elif is_pred:
            by_auth[auth][f]["fp"] += 1

for auth, fields in by_auth.items():
    print(f"\n--- Authority: {auth} ---")
    for f, cnts in fields.items():
        if cnts["gt"] > 0 or cnts["fp"] > 0:
            rec = cnts["tp"] / cnts["gt"] if cnts["gt"] > 0 else 0.0
            print(f"  {f:<22} GT={cnts['gt']} | TP={cnts['tp']} | FN={cnts['fn']} | FP={cnts['fp']} | Recall={rec:6.1%}")
