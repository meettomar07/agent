import fitz
from pathlib import Path
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

notices_dir = Path("data/generalization_notices")
with open('GENERALIZATION_SET_MANIFEST.json', encoding='utf-8') as f:
    manifest = json.load(f)

# Candidate pattern
pat = r"(?:Date\s*(?:and\s*Time\s*)?of\s*(?:[A-Za-z\(\)\/\s]{0,40})?Examination|Examination\s*Schedule)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,10}?\s*([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4})"

for idx in range(1, 10):
    fname = next(fn for fn in manifest['documents'].keys() if fn.startswith(f"gen_{idx:02d}_"))
    fpath = notices_dir / fname
    doc = fitz.open(fpath)
    gt_date = manifest['documents'][fname]['ground_truth_facts'].get('exam_date')
    
    match_val = None
    for pidx in range(min(5, len(doc))):
        text = doc[pidx].get_text()
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            match_val = m.group(1)
            break
            
    print(f"NOTICE #{idx:02d}: Expected: {gt_date:12} | Extracted: {str(match_val):12} | Match: {match_val == gt_date}")
