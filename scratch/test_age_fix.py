import fitz
from pathlib import Path
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "d:/Agent")

from testkart_intelligence.extraction.table_extractor import TableExtractor, TableExtractionResult

notices_dir = Path("data/generalization_notices")

for fname in ["gen_02_tnpsc_tourist_officer.pdf", "gen_04_tnpsc_junior_scientific_officer.pdf", "gen_06_tnpsc_civil_judge_in_tamil_nadu_stat.pdf"]:
    fpath = notices_dir / fname
    doc = fitz.open(fpath)
    tables = TableExtractor.extract_tables_from_doc(doc)
    res = TableExtractor.parse_tables(tables)
    print(f"{fname}:")
    print(f"  Age Limit: {res.age_limit}")
    print(f"  Evidence : {res.age_limit_evidence}")
