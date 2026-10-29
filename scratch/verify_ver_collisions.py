import hashlib
import json
from pathlib import Path
import fitz

frozen_hashes = set()
for manifest_name in [
    "DEVELOPMENT_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json"
]:
    with open(manifest_name, "r", encoding="utf-8") as f:
        m = json.load(f)
        for doc_name, meta in m["documents"].items():
            h = meta.get("sha256")
            if h:
                frozen_hashes.add(h.lower())

print(f"Total frozen hashes: {len(frozen_hashes)}")

ver_dir = Path("data/verification_notices")
ver_files = sorted(list(ver_dir.iterdir()))

print(f"Total verification notices: {len(ver_files)}")

for f in ver_files:
    fb = f.read_bytes()
    h = hashlib.sha256(fb).hexdigest().lower()
    assert h not in frozen_hashes, f"COLLISION with {f.name}"
    print(f"{f.name:50} | Hash: {h[:12]} | Size: {len(fb):,} bytes | COLLISION: False")

print("\nALL 11 NOTICES HAVE ZERO HASH COLLISIONS WITH ALL BENCHMARK MANIFESTS.")
