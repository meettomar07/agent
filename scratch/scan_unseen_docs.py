import json
import hashlib
from pathlib import Path

# Load all hashes from the 6 manifests
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

print(f"Total manifest hashes: {len(all_hashes)}")

# Scan data/documents
doc_dir = Path("data/documents")
all_doc_files = list(doc_dir.glob("*.pdf"))
print(f"Total files in data/documents: {len(all_doc_files)}")

available_unseen = []
for f in all_doc_files:
    # Filename is sha256.pdf
    stem = f.stem.lower().strip()
    if stem not in all_hashes:
        # verify actual hash
        actual_hash = hashlib.sha256(f.read_bytes()).hexdigest().lower()
        if actual_hash not in all_hashes:
            available_unseen.append((f, actual_hash, f.stat().st_size))

print(f"Available unseen files in data/documents: {len(available_unseen)}")
