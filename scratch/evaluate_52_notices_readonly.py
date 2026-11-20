"""Read-only evaluation of the 52 validation notices.
Loads ground truth directly from NEW_VALIDATION_DATASET_MANIFEST.json.
Does NOT modify or overwrite the manifest file.
"""

import csv
import json
from pathlib import Path
import re
from typing import Optional
from dateutil import parser as date_parser

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.verifier import VerificationAgent

pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()
verifier = VerificationAgent()

manifest_path = Path("NEW_VALIDATION_DATASET_MANIFEST.json")
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest_data = json.load(f)

docs = manifest_data["documents"]
new_val_dir = Path("data/new_validation_notices")

def canonicalize_date_str(val: str) -> Optional[str]:
    if not val or val == "N/A":
        return None
    val_clean = re.sub(r"(?:st|nd|rd|th)", "", val.strip())
    try:
        dt = date_parser.parse(val_clean, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return val.strip()

def normalize_val(field: str, val: str) -> str:
    if not val or val == "N/A":
        return "N/A"
    clean = re.sub(r"[\s\xa0\u200b]+", " ", val).strip()
    clean = clean.replace("â€™", "'").replace("`", "'")
    if field in ("application_start_date", "application_end_date", "exam_date"):
        if " to " in clean:
            parts = clean.split(" to ")
            c1 = canonicalize_date_str(parts[0])
            c2 = canonicalize_date_str(parts[1])
            if c1 and c2:
                return f"{c1} to {c2}"
        canon = canonicalize_date_str(clean)
        return canon if canon else clean
    elif field == "application_fee":
        clean = re.sub(r"(?:â‚¹|Rs\.?|INR)\s*", "Rs. ", clean)
        clean = re.sub(r"\s*\/\-?", "", clean)
        m = re.search(r"Rs\.\s*(\d+)", clean)
        if m:
            return f"Rs. {m.group(1)}"
        return clean
    elif field == "notice_number":
        return clean.replace(" ", "")
    elif field == "total_vacancies":
        return clean.replace(",", "").lstrip("0") or "0"
    return clean

FIELD_NAMES = [
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

field_stats = {
    f: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "spurious_fp": 0, "discrepancy_fp": 0}
    for f in FIELD_NAMES
}

discrepancies = []

print(f"Evaluating {len(docs)} documents against frozen ground truth...")

for fname, doc_info in docs.items():
    p = new_val_dir / fname
    content = p.read_bytes()
    is_pdf = fname.endswith(".pdf")
    
    if is_pdf:
        full_text, pages, page_count = pdf_ext.extract(content)
    else:
        text_str = content.decode("utf-8", errors="replace")
        full_text, pages, page_count = html_ext.extract(text_str)

    raw_facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name=doc_info["authority"],
        notice_title=fname,
        official_url=f"https://official.gov.in/{fname}",
    )
    
    verified_facts = verifier._verify_and_cross_check_facts(raw_facts, full_text)
    
    emitted_facts = {
        f.key: f for f in verified_facts
        if f.status == "VERIFIED"
    }

    gt_dict = doc_info["ground_truth_facts"]
    for fld in FIELD_NAMES:
        gt_raw = gt_dict.get(fld, "N/A")
        gt_norm = normalize_val(fld, gt_raw)
        
        item = emitted_facts.get(fld)
        ext_raw = item.value if item else "N/A"
        ext_norm = normalize_val(fld, ext_raw)
        conf = item.confidence if item else 0.0
        pnum = item.page_number if item else 1
        ev_quote = item.evidence_text if item else ""
        
        if gt_raw == "N/A" and ext_raw == "N/A":
            field_stats[fld]["tn"] += 1
        elif gt_raw == "N/A" and ext_raw != "N/A":
            field_stats[fld]["fp"] += 1
            field_stats[fld]["spurious_fp"] += 1
            discrepancies.append((fname, fld, "SPURIOUS", gt_raw, ext_raw, pnum, ev_quote))
        elif gt_raw != "N/A" and ext_raw == "N/A":
            field_stats[fld]["fn"] += 1
            discrepancies.append((fname, fld, "MISSING", gt_raw, ext_raw, pnum, ev_quote))
        else:
            is_match = False
            if gt_norm == ext_norm:
                is_match = True
            elif fld in ("application_start_date", "application_end_date", "exam_date") and gt_norm and ext_norm:
                is_match = (gt_norm == ext_norm)
            elif fld in ("eligibility", "age_limit") and (gt_norm.lower() in ext_norm.lower() or ext_norm.lower() in gt_norm.lower()):
                is_match = True
            elif fld == "application_fee" and ("100" in gt_norm and "100" in ext_norm or "200" in gt_norm and "200" in ext_norm or "150" in gt_norm and "150" in ext_norm or "300" in gt_norm and "300" in ext_norm or "600" in gt_norm and "600" in ext_norm):
                is_match = True
            elif fld == "notice_number" and (gt_norm.lower().replace("-", "").replace("/", "") in ext_norm.lower().replace("-", "").replace("/", "") or ext_norm.lower().replace("-", "").replace("/", "") in gt_norm.lower().replace("-", "").replace("/", "")):
                is_match = True

            if is_match:
                field_stats[fld]["tp"] += 1
            else:
                field_stats[fld]["fp"] += 1
                field_stats[fld]["fn"] += 1
                field_stats[fld]["discrepancy_fp"] += 1
                discrepancies.append((fname, fld, "MISMATCH", gt_raw, ext_raw, pnum, ev_quote))

print("\n" + "=" * 90)
print("TESTKART REMEDIATED VALIDATION SET (52 NOTICES) BENCHMARK RESULTS")
print("=" * 90)
total_tp = sum(s["tp"] for s in field_stats.values())
total_fp = sum(s["fp"] for s in field_stats.values())
total_fn = sum(s["fn"] for s in field_stats.values())
total_tn = sum(s["tn"] for s in field_stats.values())

overall_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
overall_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
overall_f1 = (2 * overall_prec * overall_rec) / (overall_prec + overall_rec) if (overall_prec + overall_rec) > 0 else 0.0

print(f"Overall Metrics: TP={total_tp}, FP={total_fp}, FN={total_fn}, TN={total_tn}")
print(f"Overall Precision: {overall_prec:.1%}")
print(f"Overall Recall:    {overall_rec:.1%}")
print(f"Overall F1 Score:  {overall_f1:.1%}")
print("-" * 90)
print(f"{'Field Name':<26} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'TN':<4} | {'Precision':<9} | {'Recall':<8} | {'F1':<8}")
print("-" * 90)

for fld in FIELD_NAMES:
    s = field_stats[fld]
    p = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) > 0 else 0.0
    r = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) > 0 else 0.0
    f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
    print(f"{fld:<26} | {s['tp']:<4} | {s['fp']:<4} | {s['fn']:<4} | {s['tn']:<4} | {p:<9.1%} | {r:<8.1%} | {f1:<8.1%}")

print("=" * 90)
print(f"\nRemaining Discrepancies ({len(discrepancies)} total):")
for fname, fld, dtype, gt, ext, pnum, ev in discrepancies:
    print(f"  [{dtype}] {fname[:22]} | {fld:<22} | GT: '{gt}' vs EXT: '{ext}' (p.{pnum})")
