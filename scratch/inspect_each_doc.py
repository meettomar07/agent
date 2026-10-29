import json
from pathlib import Path
import re

with open("scratch/new_dataset_extracted_raw.json", "r", encoding="utf-8") as f:
    docs = json.load(f)

print(f"Total documents to annotate: {len(docs)}")

# Let's write an inspector script to check each document's text and confirm ground truth
for d in docs:
    fname = d["file_name"]
    txt = d["text_preview"]
    ext = d["extracted_facts"]
    # print summary of text and extracted
    print(f"\n=== {fname} ({d['authority']}) ===")
    print(f"Format: {d['format']} | Scanned: {d['is_scanned']} | Chars: {d['chars']}")
    print(f"Preview: {txt[:200]}")
    print(f"Extracted: {ext}")
