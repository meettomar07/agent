"""Prototype script for table extraction across development notices."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pymupdf

def clean_cell(cell: Optional[str]) -> str:
    if not cell:
        return ""
    # Replace non-breaking spaces and collapse whitespace
    c = cell.replace("\xa0", " ").replace("\r", " ").replace("\n", " ")
    return " ".join(c.split())

def extract_tables_from_doc(doc: Any) -> List[Dict[str, Any]]:
    extracted_tables = []
    
    for pno in range(len(doc)):
        page = doc[pno]
        try:
            tabs = page.find_tables()
            for t_idx, t in enumerate(tabs):
                raw_rows = t.extract()
                if not raw_rows or len(raw_rows) < 2:
                    continue
                cleaned_rows = [[clean_cell(c) for c in row] if row else [] for row in raw_rows]
                # Filter empty rows
                cleaned_rows = [r for r in cleaned_rows if any(r)]
                if len(cleaned_rows) < 2:
                    continue
                header = cleaned_rows[0]
                extracted_tables.append({
                    "page_number": pno + 1,
                    "table_index": t_idx + 1,
                    "header": header,
                    "rows": cleaned_rows,
                    "row_count": len(cleaned_rows),
                    "col_count": len(header),
                })
        except Exception as e:
            continue
            
    return extracted_tables

def inspect_vacancies_in_tables(tables: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Inspect tables for explicit Total or Grand Total rows."""
    for t in tables:
        rows = t["rows"]
        for r_idx, r in enumerate(rows):
            # Check if any cell in the row marks a Total / Grand Total
            row_text = " | ".join(r)
            for c_idx, cell in enumerate(r[:4]): # Total is usually in the first few columns
                c_clean = cell.lower().strip(".:- ")
                if c_clean in ("total", "grand total", "aggregate", "total vacancies", "all posts"):
                    # Find candidate numeric value in this row
                    for val_cell in r[c_idx+1:]:
                        val_clean = val_cell.replace(",", "").strip()
                        # Extract first standalone integer
                        m = re.search(r"^\s*([0-9]{1,6})\s*(?:\*.*)?$", val_clean)
                        if m:
                            val_int = int(m.group(1))
                            if 0 < val_int < 100000:
                                return {
                                    "value": str(val_int),
                                    "page_number": t["page_number"],
                                    "evidence": f"Table Row: {row_text}",
                                    "source": "TABLE_TOTAL_ROW",
                                }
    return None

if __name__ == "__main__":
    for f in ["dev_08_tnpsc_ctse_diploma_recruitment.pdf", "dev_09_tnpsc_cts_non_interview_posts.pdf"]:
        p = Path("data/development_notices") / f
        doc = pymupdf.open(str(p))
        print("=" * 80)
        print(f"File: {f} (Pages: {len(doc)})")
        tables = extract_tables_from_doc(doc)
        print(f"Extracted {len(tables)} tables")
        vac = inspect_vacancies_in_tables(tables)
        print(f"Vacancy Result: {vac}")
