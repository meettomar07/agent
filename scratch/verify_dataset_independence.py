import hashlib
import json
from pathlib import Path

# Load frozen held-out manifest
with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
    frozen_manifest = json.load(f)
frozen_hashes = {d["sha256"]: name for name, d in frozen_manifest["documents"].items()}

# Load dev manifest
with open("DEVELOPMENT_SET_MANIFEST.json", "r", encoding="utf-8") as f:
    dev_manifest = json.load(f)
dev_hashes = {d["sha256"]: name for name, d in dev_manifest["documents"].items()}

new_val_dir = Path("data/new_validation_notices")
new_val_files = sorted(list(new_val_dir.glob("*")))

print(f"Total files in new_validation_notices: {len(new_val_files)}")
assert len(new_val_files) >= 50, f"Expected at least 50 notices, got {len(new_val_files)}"

new_hashes = {}
collisions_frozen = []
collisions_dev = []
internal_duplicates = []

for p in new_val_files:
    content = p.read_bytes()
    h = hashlib.sha256(content).hexdigest()
    if h in frozen_hashes:
        collisions_frozen.append((p.name, frozen_hashes[h]))
    if h in dev_hashes:
        collisions_dev.append((p.name, dev_hashes[h]))
    if h in new_hashes:
        internal_duplicates.append((p.name, new_hashes[h]))
    new_hashes[h] = p.name

print(f"Collisions with Frozen Held-Out Set: {len(collisions_frozen)}")
print(f"Collisions with Development Set: {len(collisions_dev)}")
print(f"Internal Duplicate Hashes: {len(internal_duplicates)}")

assert len(collisions_frozen) == 0, f"Frozen collision: {collisions_frozen}"
assert len(collisions_dev) == 0, f"Dev collision: {collisions_dev}"
assert len(internal_duplicates) == 0, f"Internal duplicate: {internal_duplicates}"
print("VERIFICATION PASSED: Complete independence and 0 hash overlap verified!")
