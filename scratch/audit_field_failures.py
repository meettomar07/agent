"""Inspect failure modes across the 33 evaluation notices."""

from pathlib import Path
import pymupdf
import re

val_dir = Path("data/validation_notices")

import sys
sys.path.insert(0, ".")
from scratch.run_held_out_evaluation_33 import GROUND_TRUTH

print("=== FAILURE MODE ANALYSIS ACROSS 33 NOTICES ===\n")

for fname, meta in GROUND_TRUTH.items():
    p = val_dir / fname
    ext = p.suffix.lower()
    content = p.read_bytes()
    is_readable = meta["readable"]
    gt = meta["facts"]
    
    # Check if this notice has applicable critical fields
    has_critical = any(gt[k] != "N/A" for k in [
        "application_start_date", "application_end_date", "total_vacancies",
        "exam_date", "application_fee", "age_limit", "eligibility"
    ])
    
    if not has_critical and is_readable:
        continue
        
    print(f"Notice: {fname} | Format: {meta['format']} | Readable: {is_readable} | Cat: {meta['category']}")
    for k in ["total_vacancies", "application_start_date", "application_end_date", "exam_date", "application_fee", "age_limit", "eligibility"]:
        if gt[k] != "N/A":
            print(f"   {k}: GT = '{gt[k]}'")
    print()
