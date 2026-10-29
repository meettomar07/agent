import json
import hashlib
from pathlib import Path
import pymupdf

# Load 145 hashes from 6 manifests
manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json",
]
all_manifest_hashes = set()
for mf in manifest_files:
    data = json.loads(Path(mf).read_text(encoding="utf-8"))
    for k, doc in data.get("documents", {}).items():
        if "sha256" in doc and doc["sha256"]:
            all_manifest_hashes.add(doc["sha256"].lower().strip())

print(f"Total manifest hashes: {len(all_manifest_hashes)}")

# Scan all 270 documents not in manifest
doc_dir = Path("data/documents")
all_files = list(doc_dir.glob("*.pdf"))

valid_docs = []
for f in all_files:
    stem = f.stem.lower().strip()
    if stem in all_manifest_hashes:
        continue
    # compute hash
    h = hashlib.sha256(f.read_bytes()).hexdigest().lower()
    if h in all_manifest_hashes:
        continue

    try:
        doc = pymupdf.open(str(f))
        if len(doc) == 0:
            continue
        full_text = ""
        for p in doc[:3]:
            full_text += (p.get_text() or "") + "\n"
        full_text_clean = " ".join(full_text.split())
        
        # Check if it's the synthetic fixture
        if "Notice No. 99/2026" in full_text_clean:
            continue
        if len(full_text_clean) < 30:
            continue

        valid_docs.append({
            "path": str(f),
            "filename": f.name,
            "sha256": h,
            "size_bytes": f.stat().st_size,
            "page_count": len(doc),
            "text": full_text_clean[:500]
        })
    except Exception as e:
        continue

print(f"Total non-synthetic real unseen docs in data/documents: {len(valid_docs)}")
with open("scratch/unseen_real_docs.json", "w", encoding="utf-8") as out:
    json.dump(valid_docs, out, indent=2)
