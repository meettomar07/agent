import json
from pathlib import Path
import fitz
from bs4 import BeautifulSoup
import sys
sys.stdout.reconfigure(encoding='utf-8')

start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
end_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 5

data_dir = Path("data/generalization_notices")
with open("scratch/harvested_generalization_candidates.json", "r", encoding="utf-8") as f:
    items = json.load(f)

for item in items:
    idx = item["index"]
    if not (start_idx <= idx <= end_idx):
        continue
    fname = item["filename"]
    fpath = data_dir / fname
    print("=" * 80)
    print(f"NOTICE #{idx:02d}: {fname} ({item['authority']})")
    print(f"Title: {item['title']}")
    print(f"URL: {item['source_url']}")
    print("-" * 80)
    
    if fname.endswith(".pdf"):
        doc = fitz.open(fpath)
        print(f"Total pages: {len(doc)}")
        full_text = ""
        for pno in range(min(5, len(doc))):
            page_text = doc[pno].get_text()
            full_text += f"\n--- PAGE {pno+1} ---\n" + page_text
        print(full_text[:3500])
    else:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        print(text[:3500])
