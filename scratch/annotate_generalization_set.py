import json
from pathlib import Path
import fitz
from bs4 import BeautifulSoup
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

data_dir = Path("data/generalization_notices")
with open("scratch/harvested_generalization_candidates.json", "r", encoding="utf-8") as f:
    items = json.load(f)

start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
end_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 5

for item in items:
    idx = item["index"]
    if not (start_idx <= idx <= end_idx):
        continue
    fname = item["filename"]
    fpath = data_dir / fname
    auth = item["authority"]
    
    print("=" * 80)
    print(f"NOTICE #{idx:02d}: {fname} | Authority: {auth}")
    print(f"Title: {item['title']}")
    
    if fname.endswith(".pdf"):
        doc = fitz.open(fpath)
        full_text = ""
        for pno in range(min(10, len(doc))):
            full_text += f"\n--- Page {pno+1} ---\n" + doc[pno].get_text()
            
        # Regex search for key sections
        # 1. Dates
        dates_block = re.search(r"(IMPORTANT DATES AND TIME|IMPORTANT DATES|Schedule|Dates).*?(?=\n\s*\d+\.\s+[A-Z]|\Z)", full_text, re.DOTALL | re.IGNORECASE)
        print("\n--- DATES BLOCK ---")
        if dates_block:
            print(dates_block.group(0)[:800])
        else:
            print("No dates block found in first 10 pages")
            
        # 2. Vacancies
        vac_block = re.search(r"(DETAILS OF VACANCIES|No\. of vacancies|Total).*?(?=\n\s*\d+\.\s+[A-Z]|\Z)", full_text, re.DOTALL | re.IGNORECASE)
        print("\n--- VACANCY BLOCK ---")
        if vac_block:
            print(vac_block.group(0)[:800])
        else:
            print("No vacancy block found")
            
        # 3. Fees
        fee_block = re.search(r"(FEES|REGISTRATION FEE|EXAMINATION FEE).*?(?=\n\s*\d+\.\s+[A-Z]|\Z)", full_text, re.DOTALL | re.IGNORECASE)
        print("\n--- FEES BLOCK ---")
        if fee_block:
            print(fee_block.group(0)[:800])
        else:
            print("No fee block found")
            
        # 4. Age Limit
        age_block = re.search(r"(AGE LIMIT|Age as on).*?(?=\n\s*\d+\.\s+[A-Z]|\Z)", full_text, re.DOTALL | re.IGNORECASE)
        print("\n--- AGE BLOCK ---")
        if age_block:
            print(age_block.group(0)[:800])
        else:
            print("No age block found")
            
        # 5. Qualification
        qual_block = re.search(r"(EDUCATIONAL QUALIFICATION|QUALIFICATION).*?(?=\n\s*\d+\.\s+[A-Z]|\Z)", full_text, re.DOTALL | re.IGNORECASE)
        print("\n--- QUALIFICATION BLOCK ---")
        if qual_block:
            print(qual_block.group(0)[:800])
        else:
            print("No qual block found")
    else:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        print("\n--- HTML CONTENT (First 1500 chars) ---")
        print(text[:1500])
