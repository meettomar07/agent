"""Deep OCR and Per-Format Audit Script.
Analyzes extraction performance separately for Scanned PDFs, Text PDFs, and HTML notices.
Inspects OCR outputs, confidence scores, and all 18 discrepancy FPs.
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
import sys
sys.path.insert(0, str(Path(".").resolve()))
sys.path.insert(0, str(Path("./scratch").resolve()))
import pymupdf
import winocr

from evaluate_new_52_dataset import NEW_GROUND_TRUTH, FIELD_NAMES
from testkart_intelligence.extraction.ocr import WindowsMediaOcrEngine, compute_ocr_confidence
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.verifier import VerificationAgent

def audit_per_format_metrics():
    print("=" * 80)
    print("AUDIT: PERFORMANCE BY DOCUMENT FORMAT (Scanned PDF vs Text PDF vs HTML)")
    print("=" * 80)

    with open("NEW_DATASET_ACCURACY_EVALUATION.csv", "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    format_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "evals": 0})
    format_field_stats = defaultdict(lambda: defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0}))

    for r in rows:
        fmt = r["document_format"]
        st = r["match_status"]
        fld = r["field_name"]

        format_stats[fmt]["evals"] += 1

        if st == "EXACT_MATCH":
            format_stats[fmt]["tp"] += 1
            format_field_stats[fmt][fld]["tp"] += 1
        elif st == "PARTIAL_OR_DISCREPANCY":
            format_stats[fmt]["fp"] += 1
            format_stats[fmt]["fn"] += 1
            format_field_stats[fmt][fld]["fp"] += 1
            format_field_stats[fmt][fld]["fn"] += 1
        elif st == "SPURIOUS_EXTRACTION":
            format_stats[fmt]["fp"] += 1
            format_field_stats[fmt][fld]["fp"] += 1
        elif st == "MISSING_IN_EXTRACTION":
            format_stats[fmt]["fn"] += 1
            format_field_stats[fmt][fld]["fn"] += 1
        elif st == "NOT_APPLICABLE_IN_NOTICE":
            format_stats[fmt]["tn"] += 1
            format_field_stats[fmt][fld]["tn"] += 1

    print(f"{'Format':<15} | {'Evals':<6} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'TN':<4} | {'Precision':<9} | {'Recall':<8} | {'F1':<8}")
    print("-" * 80)
    for fmt, s in sorted(format_stats.items()):
        p = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) > 0 else 0.0
        r = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        print(f"{fmt:<15} | {s['evals']:<6} | {s['tp']:<4} | {s['fp']:<4} | {s['fn']:<4} | {s['tn']:<4} | {p:<9.1%} | {r:<8.1%} | {f1:<8.1%}")

    print("\nFormat Specific Field Details:")
    for fmt in sorted(format_stats.keys()):
        print(f"\n--- {fmt} (Notices: {len([m for m in NEW_GROUND_TRUTH.values() if m['format'] == fmt])}) ---")
        print(f"{'Field':<25} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'TN':<4} | {'Precision':<9} | {'Recall':<8}")
        for fld in FIELD_NAMES:
            fs = format_field_stats[fmt][fld]
            p = fs["tp"] / (fs["tp"] + fs["fp"]) if (fs["tp"] + fs["fp"]) > 0 else 0.0
            r = fs["tp"] / (fs["tp"] + fs["fn"]) if (fs["tp"] + fs["fn"]) > 0 else 0.0
            print(f"{fld:<25} | {fs['tp']:<4} | {fs['fp']:<4} | {fs['fn']:<4} | {fs['tn']:<4} | {p:<9.1%} | {r:<8.1%}")


def audit_scanned_pdf_ocr_details():
    print("\n" + "=" * 80)
    print("AUDIT: 10 SCANNED PDFS OCR QUALITY AND EXTRACTIONS")
    print("=" * 80)

    val_dir = Path("data/new_validation_notices")
    pdf_ext = PdfDocumentExtractor()
    ocr_engine = WindowsMediaOcrEngine()

    scanned_files = [fname for fname, m in NEW_GROUND_TRUTH.items() if m["format"] == "SCANNED_PDF"]
    print(f"Total Scanned PDFs: {len(scanned_files)}")

    for idx, fname in enumerate(scanned_files, 1):
        p = val_dir / fname
        bytes_data = p.read_bytes()
        doc = pymupdf.open(stream=bytes_data, filetype="pdf")
        page_count = len(doc)

        # PyMuPDF direct text
        raw_text_pymupdf = "".join(page.get_text() for page in doc).strip()
        doc.close()

        # Run extractor
        full_text, pages, count = pdf_ext.extract(bytes_data)

        # Compute average confidence and character stats
        avg_conf = sum(page.get("ocr_confidence", 0.0) for page in pages) / max(1, len(pages))
        total_ocr_chars = len(full_text.strip())

        meta = NEW_GROUND_TRUTH[fname]
        print(f"\n[{idx}/10] {fname}")
        print(f"    Authority: {meta['authority']}")
        print(f"    Category: {meta['category']}")
        print(f"    Pages: {page_count} | PyMuPDF text len: {len(raw_text_pymupdf)} (scanned: {len(raw_text_pymupdf) < 50})")
        print(f"    OCR extracted chars: {total_ocr_chars} | Avg OCR confidence: {avg_conf:.3f}")
        print(f"    Sample OCR Text: {repr(full_text[:120])}")
        print(f"    Ground Truth Facts:")
        for k, v in meta["facts"].items():
            if v != "N/A":
                print(f"      * {k}: {v}")

def audit_all_false_positives():
    print("\n" + "=" * 80)
    print("AUDIT: DETAILED ANALYSIS OF ALL 18 FALSE POSITIVES")
    print("=" * 80)

    with open("NEW_DATASET_ACCURACY_EVALUATION.csv", "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    fp_rows = [r for r in rows if r["match_status"] in ("PARTIAL_OR_DISCREPANCY", "SPURIOUS_EXTRACTION")]
    print(f"Total False Positives: {len(fp_rows)}")

    for idx, r in enumerate(fp_rows, 1):
        print(f"\nFP #{idx}: Field='{r['field_name']}' | Status='{r['match_status']}'")
        print(f"   Notice: {r['notice_file']} ({r['authority']})")
        print(f"   Ground Truth: '{r['ground_truth_value']}'")
        print(f"   Extracted:    '{r['extracted_value']}'")
        print(f"   Confidence:   {r['confidence']} | Page: {r['page_number']}")
        ev_safe = r['evidence_quote'].encode('ascii', 'replace').decode('ascii')
        print(f"   Evidence:     {ev_safe}")

if __name__ == "__main__":
    audit_all_false_positives()
