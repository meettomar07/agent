import json
import hashlib
import re
from pathlib import Path
import pymupdf

# Load all hashes from 6 manifests
manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json",
]

all_hashes = set()
for mf in manifest_files:
    p = Path(mf)
    if not p.exists():
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    for k, doc in data.get("documents", {}).items():
        if "sha256" in doc and doc["sha256"]:
            all_hashes.add(doc["sha256"].lower().strip())

doc_dir = Path("data/documents")
all_files = list(doc_dir.glob("*.pdf"))

candidates = []
for f in all_files:
    stem = f.stem.lower().strip()
    if stem in all_hashes:
        continue
    
    # Read first page of PDF
    try:
        doc = pymupdf.open(str(f))
        if len(doc) == 0:
            continue
        first_page = doc[0].get_text() or ""
        first_page_clean = " ".join(first_page.split())
        
        # Identify authority
        auth = None
        source_id = None
        txt_lower = first_page_clean.lower()
        
        if "staff selection commission" in txt_lower or "ssc" in txt_lower:
            auth = "Staff Selection Commission"
            source_id = "src_ssc"
        elif "union public service commission" in txt_lower or "upsc" in txt_lower or "dholpur house" in txt_lower:
            auth = "Union Public Service Commission"
            source_id = "src_upsc"
        elif "national testing agency" in txt_lower or "nta" in txt_lower:
            auth = "National Testing Agency"
            source_id = "src_nta"
        elif "uttar pradesh public service commission" in txt_lower or "uppsc" in txt_lower or "prayagraj" in txt_lower:
            auth = "Uttar Pradesh Public Service Commission"
            source_id = "src_uppsc"
        elif "tamil nadu public service commission" in txt_lower or "tnpsc" in txt_lower or "chennai" in txt_lower:
            auth = "Tamil Nadu Public Service Commission"
            source_id = "src_tnpsc"
            
        if auth:
            # Extract possible title
            candidates.append({
                "file": f.name,
                "path": str(f),
                "sha256": stem,
                "size_bytes": f.stat().st_size,
                "pages": len(doc),
                "source_id": source_id,
                "authority": auth,
                "snippet": first_page_clean[:250]
            })
    except Exception as e:
        continue

print(f"Discovered {len(candidates)} classified candidate documents from 5 authorities!")
by_auth = {}
for c in candidates:
    by_auth.setdefault(c["source_id"], []).append(c)

for s_id, items in by_auth.items():
    print(f"  {s_id}: {len(items)} documents")

with open("scratch/candidates_found.json", "w", encoding="utf-8") as out:
    json.dump(candidates, out, indent=2)
