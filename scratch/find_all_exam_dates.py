import fitz
from pathlib import Path
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

notices_dir = Path("data/generalization_notices")
with open('GENERALIZATION_SET_MANIFEST.json', encoding='utf-8') as f:
    manifest = json.load(f)

for idx in range(1, 10):
    fname = next(fn for fn in manifest['documents'].keys() if fn.startswith(f"gen_{idx:02d}_"))
    fpath = notices_dir / fname
    gt_date = manifest['documents'][fname]['ground_truth_facts'].get('exam_date')
    
    doc = fitz.open(fpath)
    print("=" * 80, flush=True)
    print(f"NOTICE #{idx:02d}: {fname} | Expected Exam Date: {gt_date}", flush=True)
    
    found = False
    for pidx, page in enumerate(doc):
        text = page.get_text()
        if gt_date in text:
            found = True
            print(f"  FOUND on Page {pidx + 1}:", flush=True)
            lines = text.split("\n")
            for lno, l in enumerate(lines):
                if gt_date in l:
                    start_l = max(0, lno - 4)
                    end_l = min(len(lines), lno + 5)
                    print("    --- Context ---", flush=True)
                    for c_idx in range(start_l, end_l):
                        prefix = ">>> " if c_idx == lno else "    "
                        print(f"{prefix}{lines[c_idx]}", flush=True)
    if not found:
        print(f"  NOT FOUND verbatim ({gt_date}) in entire document!", flush=True)
