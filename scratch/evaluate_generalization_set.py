import csv
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "d:/Agent")

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()

MANIFEST_PATH = Path("GENERALIZATION_SET_MANIFEST.json")
NOTICES_DIR = Path("data/generalization_notices")
OUT_CSV = Path("INDEPENDENT_GENERALIZATION_EVALUATION.csv")

with open(MANIFEST_PATH, encoding="utf-8") as f:
    manifest = json.load(f)

docs = manifest.get("documents", {})

ALL_FIELDS = [
    "recruiting_authority",
    "notice_number",
    "application_start_date",
    "application_end_date",
    "total_vacancies",
    "exam_date",
    "application_fee",
    "age_limit",
    "eligibility",
]

def normalize(v):
    if v is None:
        return ""
    v = str(v).strip().lower()
    v = re.sub(r"[\s,/\-.]+", " ", v).strip()
    v = re.sub(r"\b(rs|inr)\b\.?", "rs", v)
    return v

def values_match(field, extracted, gt):
    if not extracted or not gt:
        return False
    e_norm = normalize(extracted)
    g_norm = normalize(gt)
    if e_norm == g_norm:
        return True
        
    # Vacancy: numeric match
    if field == "total_vacancies":
        e_digits = re.sub(r"[^0-9]", "", e_norm)
        g_digits = re.sub(r"[^0-9]", "", g_norm)
        if e_digits and g_digits:
            try:
                if int(e_digits) == int(g_digits):
                    return True
            except ValueError:
                if e_digits == g_digits:
                    return True

    # Date match: check for matching dates
    if "date" in field:
        def extract_dates(s):
            return set(re.findall(r"\d{1,2}[./\-]\d{1,2}[./\-]\d{4}", s))
        e_dates = extract_dates(e_norm)
        g_dates = extract_dates(g_norm)
        if e_dates and g_dates and (e_dates & g_dates):
            return True

    # Eligibility: substring containment if substantial length
    if field == "eligibility":
        if len(g_norm) >= 8 and (g_norm in e_norm or e_norm in g_norm):
            return True
        words_g = set(w for w in g_norm.split() if len(w) > 3)
        words_e = set(w for w in e_norm.split() if len(w) > 3)
        if words_g and len(words_g & words_e) >= min(2, len(words_g)):
            return True

    # Age limit: substring containment or number match
    if field == "age_limit":
        e_nums = re.findall(r"\d+", e_norm)
        g_nums = re.findall(r"\d+", g_norm)
        if e_nums and g_nums and e_nums[-1] == g_nums[-1]: # match max age
            return True
        if g_norm in e_norm or e_norm in g_norm:
            return True

    # Fee: match digits
    if field == "application_fee":
        e_fee = re.findall(r"\d+", e_norm)
        g_fee = re.findall(r"\d+", g_norm)
        if e_fee and g_fee and e_fee[0] == g_fee[0]:
            return True

    # Authority: substring match
    if field == "recruiting_authority":
        if g_norm in e_norm or e_norm in g_norm:
            return True

    # Notice number: alphanumeric match
    if field == "notice_number":
        e_clean = re.sub(r"[^a-z0-9]", "", e_norm)
        g_clean = re.sub(r"[^a-z0-9]", "", g_norm)
        if e_clean and g_clean and (e_clean == g_clean or g_clean in e_clean or e_clean in g_clean):
            return True

    return False

rows_out = []
field_stats = defaultdict(lambda: {
    "EXACT_MATCH": 0,
    "PARTIAL_OR_DISCREPANCY": 0,
    "MISSING_IN_EXTRACTION": 0,
    "SPURIOUS_EXTRACTION": 0,
    "NOT_APPLICABLE_IN_NOTICE": 0
})

print(f"Starting evaluation of {len(docs)} notices...")

for fname, meta in docs.items():
    fpath = NOTICES_DIR / fname
    authority = meta.get("authority", "Unknown")
    gt = meta.get("ground_truth_facts", {})
    format_type = meta.get("format", "TEXT_PDF")
    is_readable = meta.get("readable", True)
    
    # Extract
    is_pdf = fname.endswith(".pdf")
    try:
        if is_pdf:
            full_text, pages, count = pdf_ext.extract(fpath.read_bytes())
        else:
            full_text, pages, count = html_ext.extract(fpath.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        print(f"Extraction error for {fname}: {exc}")
        pages = []
        count = 0
        
    facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name=authority,
        notice_title=fname,
        official_url=f"https://official.gov.in/{fname}"
    )
    fact_dict = {f.key: f.value for f in facts}
    evidence_dict = {f.key: f.evidence_text for f in facts}
    conf_dict = {f.key: f.confidence for f in facts}

    for fld in ALL_FIELDS:
        gt_val = gt.get(fld, "N/A")
        ext_val = fact_dict.get(fld, "")
        ev_text = evidence_dict.get(fld, "")
        conf = conf_dict.get(fld, 0.0)

        is_gt_na = (gt_val == "N/A" or not gt_val)
        is_ext_empty = (not ext_val or ext_val == "N/A")

        if is_gt_na:
            if is_ext_empty:
                status = "NOT_APPLICABLE_IN_NOTICE"
                field_stats[fld]["NOT_APPLICABLE_IN_NOTICE"] += 1
            else:
                status = "SPURIOUS_EXTRACTION"
                field_stats[fld]["SPURIOUS_EXTRACTION"] += 1
        else:
            if is_ext_empty:
                status = "MISSING_IN_EXTRACTION"
                field_stats[fld]["MISSING_IN_EXTRACTION"] += 1
            else:
                if values_match(fld, ext_val, gt_val):
                    status = "EXACT_MATCH"
                    field_stats[fld]["EXACT_MATCH"] += 1
                else:
                    status = "PARTIAL_OR_DISCREPANCY"
                    field_stats[fld]["PARTIAL_OR_DISCREPANCY"] += 1

        rows_out.append({
            "notice_file": fname,
            "authority": authority,
            "format": format_type,
            "readable": is_readable,
            "field_name": fld,
            "ground_truth_value": gt_val,
            "extracted_value": ext_val,
            "match_status": status,
            "confidence": conf,
            "evidence_text": (ev_text[:120] if ev_text else "")
        })

# Write CSV
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "notice_file", "authority", "format", "readable", "field_name",
        "ground_truth_value", "extracted_value", "match_status", "confidence", "evidence_text"
    ])
    writer.writeheader()
    writer.writerows(rows_out)

print(f"\nSaved evaluation CSV to {OUT_CSV} with {len(rows_out)} rows.")

# Print Summary Table
print("\n" + "=" * 95)
print(f"{'Field':<25} | {'Exact(TP)':<10} | {'Discrep(FP/FN)':<15} | {'Missing(FN)':<12} | {'Spurious(FP)':<12} | {'NotApp(TN)':<10}")
print("=" * 95)
for fld in ALL_FIELDS:
    s = field_stats[fld]
    print(f"{fld:<25} | {s['EXACT_MATCH']:<10} | {s['PARTIAL_OR_DISCREPANCY']:<15} | {s['MISSING_IN_EXTRACTION']:<12} | {s['SPURIOUS_EXTRACTION']:<12} | {s['NOT_APPLICABLE_IN_NOTICE']:<10}")
print("=" * 95)

print("\nRecalculated Evaluation Metrics (Independent Generalization Benchmark):")
print(f"{'Field':<25} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'TN':<4} | {'Precision':<9} | {'Recall':<8} | {'F1':<8} | {'OmissionAcc':<11}")
print("-" * 95)

total_tp = total_fp = total_fn = total_tn = 0
precisions, recalls, f1s = [], [], []

for fld in ALL_FIELDS:
    s = field_stats[fld]
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
    omission_acc = tn / (tn + s["SPURIOUS_EXTRACTION"]) if (tn + s["SPURIOUS_EXTRACTION"]) > 0 else 1.0
    
    precisions.append(p)
    recalls.append(r)
    f1s.append(f1)
    
    print(f"{fld:<25} | {tp:<4} | {fp:<4} | {fn:<4} | {tn:<4} | {p:<9.1%} | {r:<8.1%} | {f1:<8.1%} | {omission_acc:<11.1%}")

print("-" * 95)
micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
micro_f1 = (2 * micro_p * micro_r) / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0
print(f"{'OVERALL (Micro-avg)':<25} | {total_tp:<4} | {total_fp:<4} | {total_fn:<4} | {total_tn:<4} | {micro_p:<9.1%} | {micro_r:<8.1%} | {micro_f1:<8.1%}")

macro_p = sum(precisions) / len(precisions)
macro_r = sum(recalls) / len(recalls)
macro_f1 = sum(f1s) / len(f1s)
print(f"{'OVERALL (Macro-avg)':<25} | {'-':<4} | {'-':<4} | {'-':<4} | {'-':<4} | {macro_p:<9.1%} | {macro_r:<8.1%} | {macro_f1:<8.1%}")
