import fitz
from pathlib import Path
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

notices_dir = Path("data/generalization_notices")
with open('GENERALIZATION_SET_MANIFEST.json', encoding='utf-8') as f:
    manifest = json.load(f)

for idx in [1, 2, 3, 4, 6]:
    fname = next(fn for fn in manifest['documents'].keys() if fn.startswith(f"gen_{idx:02d}_"))
    fpath = notices_dir / fname
    doc = fitz.open(fpath)
    print("=" * 80)
    print(f"NOTICE #{idx:02d}: {fname}")
    for pidx in range(min(4, len(doc))):
        page = doc[pidx]
        tabs = page.find_tables()
        if tabs.tables:
            print(f"  Page {pidx + 1}: Found {len(tabs.tables)} tables")
            for t_idx, t in enumerate(tabs.tables):
                extracted = t.extract()
                print(f"    Table {t_idx + 1} ({len(extracted)} rows):")
                for row_idx, row in enumerate(extracted[:8]):
                    print(f"      Row {row_idx}: {row}")
        else:
            print(f"  Page {pidx + 1}: NO tables detected by find_tables()")
