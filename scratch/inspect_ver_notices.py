import fitz
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ver_dir = Path("data/verification_notices")

for f in sorted(ver_dir.iterdir()):
    print("=" * 80)
    print(f"NOTICE: {f.name} ({f.stat().st_size:,} bytes)")
    if f.suffix == ".pdf":
        doc = fitz.open(f)
        print(f"Pages: {len(doc)}")
        for p in range(min(4, len(doc))):
            t = doc[p].get_text().strip()
            if t:
                print(f"--- Page {p+1} (first 600 chars) ---")
                print(t[:600])
    else:
        text = f.read_text(encoding='utf-8', errors='ignore')
        print(text[:600])
