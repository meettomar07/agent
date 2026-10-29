import fitz
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "d:/Agent")
from testkart_intelligence.extraction.table_extractor import TableExtractor

for fname in ["gen_02_tnpsc_tourist_officer.pdf", "gen_04_tnpsc_junior_scientific_officer.pdf", "gen_06_tnpsc_civil_judge_in_tamil_nadu_stat.pdf"]:
    doc = fitz.open(f"data/generalization_notices/{fname}")
    tables = TableExtractor.extract_tables_from_doc(doc)
    print("=" * 80)
    print(fname)
    for t in tables:
        h = " | ".join(t["header"]).lower()
        if "age" in h:
            print(f"Table on page {t['page_number']}:")
            for r in t["rows"]:
                print("  ", r)
