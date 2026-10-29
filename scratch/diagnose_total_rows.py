"""
Deep diagnosis of vacancy table total extraction failures.
Scans all tables in selected new_val PDFs to see what total rows exist.
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, 'd:/Agent')

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.table_extractor import TableExtractor

pdf_ext = PdfDocumentExtractor()

test_cases = {
    "new_val_01_tnpsc_combined_civil_services_examin.pdf": 35,
    "new_val_02_tnpsc_assistant_public_prosecutor__g.pdf": 50,
    "new_val_03_tnpsc_combined_technical_services_ex.pdf": 22,
    "new_val_04_tnpsc_combined_technical_services_ex.pdf": 118,
    "new_val_05_tnpsc_combined_civil_services_examin.pdf": 29,
    "new_val_09_tnpsc_assistant_agricultural_officer.pdf": 263,
    "new_val_10_tnpsc_combined_accounts_services_exa.pdf": 52,
    "new_val_16_tnpsc_research_assistant_in_the_inst.pdf": 6,
}

import re

def find_all_total_rows(tables):
    """Find every row across all tables that looks like a total row."""
    results = []
    for t in tables:
        pno = t["page_number"]
        for r in t["rows"]:
            if len(r) < 2:
                continue
            row_str = " | ".join(r)
            for c_idx in range(min(5, len(r))):
                cell_clean = r[c_idx].strip().lower().strip(".:- ")
                if (cell_clean in ("total", "grand total", "aggregate", "total vacancies",
                                   "all posts", "sum total", "total posts")
                    or (cell_clean.startswith("total") and "mark" not in cell_clean
                        and "question" not in cell_clean and len(cell_clean) < 20)):
                    # Extract all numeric values from the rest of the row
                    nums = []
                    for vc in r[c_idx+1:]:
                        cleaned = vc.replace(",","").strip()
                        m = re.match(r"^([0-9]{1,6})(?:\s*[\*\#\@]+.*)?$", cleaned)
                        if m:
                            n = int(m.group(1))
                            if 0 < n < 500000:
                                nums.append(n)
                    if nums:
                        results.append({
                            "page": pno,
                            "label": r[c_idx].strip(),
                            "numbers": nums,
                            "first_num": nums[0],
                            "max_num": max(nums),
                            "row_preview": row_str[:100],
                        })
    return results

for fname, gt in test_cases.items():
    fpath = Path("data/new_validation_notices") / fname
    if not fpath.exists():
        print(f"\n{fname}: FILE NOT FOUND")
        continue
    full_text, pages, count = pdf_ext.extract(fpath.read_bytes())
    doc_tables = pages[0].get("document_tables", [])
    total_rows = find_all_total_rows(doc_tables)
    print(f"\n{'='*60}")
    print(f"{fname}")
    print(f"  GT: {gt} | Tables found: {len(doc_tables)}")
    print(f"  All total rows found ({len(total_rows)}):")
    for tr in total_rows:
        marker = " <-- CORRECT" if gt in tr["numbers"] else ""
        print(f"    Page {tr['page']}: [{tr['label']}] nums={tr['numbers']}{marker}")
        print(f"      Row: {tr['row_preview']}")
