import sys
import fitz
from bs4 import BeautifulSoup
from pathlib import Path
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/harvested_generalization_candidates.json", "r", encoding="utf-8") as f:
    items = json.load(f)

start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 7
end_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 11

for item in items:
    idx = item["index"]
    if not (start_idx <= idx <= end_idx):
        continue
    fname = item["filename"]
    fpath = Path("data/generalization_notices") / fname
    auth = item["authority"]
    title = item["title"]
    
    print("\n" + "=" * 80)
    print(f"NOTICE #{idx:02d}: {fname} | Authority: {auth}")
    print(f"Title: {title}")
    
    if fname.endswith(".pdf"):
        doc = fitz.open(fpath)
        first_pages = ""
        for p in range(min(5, len(doc))):
            first_pages += f"\n--- P.{p+1} ---\n" + doc[p].get_text()
            
        # Extract Notification No.
        m_notif = re.search(r"Notification\s+No\.?\s*:?\s*([0-9A-Za-z/_\-]+)", first_pages, re.I)
        notif_no = m_notif.group(1) if m_notif else "N/A"
        
        # Extract Dated
        m_date = re.search(r"DATED\s*:?\s*([0-9]{2}[\./\-][0-9]{2}[\./\-][0-9]{4})", first_pages, re.I)
        dated = m_date.group(1) if m_date else "N/A"
        
        # Extract Last Date
        m_last = re.search(r"(?:upto|up to|last date.*?)\s+([0-9]{2}[\./\-][0-9]{2}[\./\-][0-9]{4})", first_pages, re.I)
        last_date = m_last.group(1) if m_last else "N/A"
        
        print(f"Extracted header hints: Notif={notif_no}, Dated={dated}, LastDate={last_date}")
        print(first_pages[:1200])
    else:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        print("HTML content preview:")
        print(text[:1200])
