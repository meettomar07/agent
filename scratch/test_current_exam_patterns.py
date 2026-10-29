import fitz
from pathlib import Path
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "d:/Agent")
from testkart_intelligence.extraction.fact_extractor import FactExtractor

notices_dir = Path("data/generalization_notices")
with open('GENERALIZATION_SET_MANIFEST.json', encoding='utf-8') as f:
    manifest = json.load(f)

for idx in range(1, 10):
    fname = next(fn for fn in manifest['documents'].keys() if fn.startswith(f"gen_{idx:02d}_"))
    fpath = notices_dir / fname
    doc = fitz.open(fpath)
    gt_date = manifest['documents'][fname]['ground_truth_facts'].get('exam_date')
    
    print("=" * 80)
    print(f"NOTICE #{idx:02d}: {fname} | Expected: {gt_date}")
    
    for pidx in range(min(5, len(doc))):
        text = doc[pidx].get_text()
        for p_i, pat in enumerate(FactExtractor.EXAM_DATE_PATTERNS):
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                print(f"  Page {pidx+1}: MATCH on Pattern {p_i}: {m.groups()}")
