import json
import hashlib
from pathlib import Path

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
    data = json.loads(Path(mf).read_text(encoding="utf-8"))
    for k, doc in data.get("documents", {}).items():
        if "sha256" in doc and doc["sha256"]:
            all_hashes.add(doc["sha256"].lower().strip())

print(f"Manifest hashes: {len(all_hashes)}")

# Scan all files in data/
all_data_files = list(Path("data").glob("**/*.*"))
print(f"Total files under data/: {len(all_data_files)}")

valid_extensions = {".pdf", ".html", ".htm", ".txt"}
found_by_dir = {}

for f in all_data_files:
    if f.suffix.lower() not in valid_extensions:
        continue
    h = hashlib.sha256(f.read_bytes()).hexdigest().lower()
    in_manifest = h in all_hashes
    d = str(f.parent)
    found_by_dir.setdefault(d, {"total": 0, "in_manifest": 0, "not_in_manifest": 0})
    found_by_dir[d]["total"] += 1
    if in_manifest:
        found_by_dir[d]["in_manifest"] += 1
    else:
        found_by_dir[d]["not_in_manifest"] += 1

for d, counts in found_by_dir.items():
    print(f"Directory '{d}': {counts}")
