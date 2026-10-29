import json
from pathlib import Path
import hashlib

frozen_hashes = set()
for manifest_name in [
    "DEVELOPMENT_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json"
]:
    with open(manifest_name, encoding="utf-8") as f:
        m = json.load(f)
        for doc_name, meta in m["documents"].items():
            h = meta.get("sha256")
            if h:
                frozen_hashes.add(h.lower())

doc_dir = Path("data/documents")
all_files = list(doc_dir.iterdir())
print(f"Total files in data/documents: {len(all_files)}")

available = []
for f in all_files:
    fname = f.name
    # File name is hash + extension or we can hash it
    file_bytes = f.read_bytes()
    chash = hashlib.sha256(file_bytes).hexdigest().lower()
    if chash not in frozen_hashes and len(file_bytes) > 20000:
        available.append((f, chash, len(file_bytes)))

print(f"Available large files not in any frozen benchmark: {len(available)}")
for f, chash, size in available[:15]:
    print(f"  {f.name} ({size:,} bytes)")
