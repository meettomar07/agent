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
    doc = fitz.open(fpath)
    print("=" * 80)
    print(f"NOTICE #{idx:02d}: {fname}")
    # Search for "IMPORTANT DATES" in pages
    for pidx in range(min(5, len(doc))):
        text = doc[pidx].get_text()
        if "IMPORTANT DATES" in text.upper():
            print(f"--- PAGE {pidx+1} ---")
            lines = text.split("\n")
            in_dates = False
            date_lines = []
            for l in lines:
                if "IMPORTANT DATES" in l.upper():
                    in_dates = True
                if in_dates:
                    date_lines.append(l)
                    if len(date_lines) > 35 or ("QUALIFICATION" in l.upper() and len(date_lines) > 5):
                        break
            print("\n".join(date_lines[:30]))
