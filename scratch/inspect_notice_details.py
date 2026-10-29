import sys
import fitz
from bs4 import BeautifulSoup
from pathlib import Path
import json

sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/harvested_generalization_candidates.json", "r", encoding="utf-8") as f:
    items = json.load(f)

notice_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
start_page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
end_page = int(sys.argv[3]) if len(sys.argv) > 3 else 5

item = next(it for it in items if it["index"] == notice_idx)
fname = item["filename"]
fpath = Path("data/generalization_notices") / fname

print(f"=== NOTICE {notice_idx}: {fname} ===")
print(f"Title: {item['title']}")
print(f"Authority: {item['authority']}")
print(f"URL: {item['source_url']}")

if fname.endswith(".pdf"):
    doc = fitz.open(fpath)
    print(f"Total pages: {len(doc)}")
    for p in range(start_page - 1, min(end_page, len(doc))):
        print(f"\n--- PAGE {p + 1} ---")
        print(doc[p].get_text())
else:
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")
    print(soup.get_text(separator="\n", strip=True))
