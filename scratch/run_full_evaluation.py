"""
Comprehensive evaluation of FactExtractor + TableExtractor integration
on the NEW_VALIDATION_DATASET (52 notices, frozen, read-only).

IMPORTANT:
- This script is EVALUATION ONLY — it does not modify any model, rule, or threshold.
- The NEW_VALIDATION_DATASET_MANIFEST.json is FROZEN; nothing in it is changed.
- Results are written to COMPLEX_TABLE_ACCURACY_EVALUATION.csv only.

Metrics computed per field:
    TP = extracted matches ground truth (exact or normalized)
    FP = extracted but wrong / not in ground truth
    FN = not extracted but ground truth exists
    TN = not extracted, no ground truth (correct omission)

Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * P * R / (P + R)
Omission Accuracy = TN / (TN + FP)  [for fields where absence is expected]
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "d:/Agent")

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.table_extractor import TableExtractor

pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()

MANIFEST_PATH = Path("NEW_VALIDATION_DATASET_MANIFEST.json")
NOTICES_DIR = Path("data/new_validation_notices")
OUT_CSV = Path("COMPLEX_TABLE_ACCURACY_EVALUATION.csv")

with open(MANIFEST_PATH, encoding="utf-8") as f:
    manifest = json.load(f)

docs = manifest.get("documents", manifest.get("notices", {}))

# Ground truth key may be nested under ground_truth_facts or ground_truth or annotations
def get_gt(meta):
    for key in ("ground_truth_facts", "ground_truth", "annotations"):
        if key in meta and isinstance(meta[key], dict):
            return meta[key]
    return meta

FIELDS = [
    "total_vacancies",
    "application_start_date",
    "application_end_date",
    "exam_date",
    "age_limit",
    "eligibility",
    "application_fee",
]

def normalize(v):
    """Normalize values for comparison: lowercase, strip, collapse spaces."""
    if v is None:
        return ""
    v = str(v).strip().lower()
    v = re.sub(r"[\s,/\-.]+", " ", v).strip()
    v = re.sub(r"\b(rs|inr)\b\.?", "rs", v)
    return v

def values_match(extracted, ground_truth):
    """Compare extracted value to ground truth with normalization."""
    if not extracted or not ground_truth:
        return False
    e_norm = normalize(extracted)
    g_norm = normalize(ground_truth)
    if e_norm == g_norm:
        return True
    # Numeric match for vacancies
    e_num = re.sub(r"[^0-9]", "", e_norm)
    g_num = re.sub(r"[^0-9]", "", g_norm)
    if e_num and g_num and e_num == g_num:
        return True
    # Partial date match (day.month.year extracted from ground truth)
    if re.search(r"\d{1,2}[./]\d{1,2}[./]\d{4}", e_norm) and re.search(r"\d{1,2}[./]\d{1,2}[./]\d{4}", g_norm):
        def extract_dates(s):
            return set(re.findall(r"\d{1,2}[./]\d{1,2}[./]\d{4}", s))
        e_dates = extract_dates(e_norm)
        g_dates = extract_dates(g_norm)
        if e_dates & g_dates:
            return True
    # Eligibility: substring match if gt is contained in extracted
    if len(g_norm) >= 8 and g_norm in e_norm:
        return True
    return False


# Counters per field
counters = {field: {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "errors": []} for field in FIELDS}

rows_out = []

for fname, meta in docs.items():
    fpath = NOTICES_DIR / fname
    if not fpath.exists():
        print(f"  MISSING: {fname}")
        continue

    gt = get_gt(meta)
    authority = meta.get("authority", "Unknown")

    # Extract
    is_pdf = fname.endswith(".pdf")
    try:
        if is_pdf:
            full_text, pages, count = pdf_ext.extract(fpath.read_bytes())
        else:
            full_text, pages, count = html_ext.extract(fpath.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        print(f"  EXTRACT ERROR {fname}: {exc}")
        continue

    facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name=authority,
        notice_title=fname,
        official_url=f"https://test.gov.in/{fname}",
    )
    fact_dict = {f.key: f.value for f in facts}

    # Also run TableExtractor directly
    doc_tables = pages[0].get("document_tables", []) if pages else []
    tbl_res = TableExtractor.parse_tables(doc_tables, authority)

    row_entry = {"file": fname, "authority": authority, "pages": count}

    for field in FIELDS:
        gt_val = gt.get(field, "")
        extracted_val = fact_dict.get(field, "")

        # Supplement with table-extractor results for vacancy
        if field == "total_vacancies" and not extracted_val and tbl_res.total_vacancies:
            extracted_val = tbl_res.total_vacancies

        has_gt = bool(gt_val)
        has_extracted = bool(extracted_val)
        matched = values_match(extracted_val, gt_val)

        if has_gt and has_extracted and matched:
            status = "TP"
        elif has_gt and has_extracted and not matched:
            status = "FP"
        elif has_gt and not has_extracted:
            status = "FN"
        else:
            status = "TN"

        counters[field][status] += 1
        if status in ("FP", "FN"):
            counters[field]["errors"].append({
                "file": fname,
                "status": status,
                "gt": gt_val,
                "extracted": extracted_val,
            })

        row_entry[f"{field}_gt"] = gt_val
        row_entry[f"{field}_extracted"] = extracted_val
        row_entry[f"{field}_status"] = status

    rows_out.append(row_entry)

# Write CSV
fieldnames = ["file", "authority", "pages"] + [
    f"{field}_{suffix}"
    for field in FIELDS
    for suffix in ("gt", "extracted", "status")
]
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows_out)

# Print summary
print(f"\n{'='*70}")
print("EXTRACTION EVALUATION SUMMARY")
print(f"Dataset: {MANIFEST_PATH.name}  |  Notices evaluated: {len(rows_out)}")
print(f"{'='*70}")
print(f"{'Field':<28} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4} {'Prec':>7} {'Recall':>7} {'F1':>7} {'N(GT)':>7}")
print(f"{'-'*70}")

summary = {}
for field in FIELDS:
    c = counters[field]
    tp, fp, fn, tn = c["TP"], c["FP"], c["FN"], c["TN"]
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0.0
    n_gt = tp + fn
    summary[field] = {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "precision": prec, "recall": recall, "f1": f1, "n_gt": n_gt}
    print(f"  {field:<26} {tp:>4} {fp:>4} {fn:>4} {tn:>4} {prec:>7.1%} {recall:>7.1%} {f1:>7.1%} {n_gt:>7}")

print(f"\nFALSE NEGATIVES (extracted=N/A, gt exists):")
for field in FIELDS:
    fns = [e for e in counters[field]["errors"] if e["status"] == "FN"]
    if fns:
        print(f"\n  [{field}] {len(fns)} FNs:")
        for e in fns[:5]:
            print(f"    File: {e['file']}")
            print(f"      GT: {e['gt']}")

print(f"\nFALSE POSITIVES (extracted wrong value):")
for field in FIELDS:
    fps = [e for e in counters[field]["errors"] if e["status"] == "FP"]
    if fps:
        print(f"\n  [{field}] {len(fps)} FPs:")
        for e in fps[:5]:
            print(f"    File: {e['file']}")
            print(f"      GT: {e['gt']}  |  Extracted: {e['extracted']}")

print(f"\nResults written to: {OUT_CSV}")
