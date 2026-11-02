import json
from pathlib import Path

manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "INDEPENDENT_ACCURACY_AUDIT_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_BATCH_2_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json"
]

all_hashes = set()
for mf in manifest_files:
    p = Path(mf)
    if not p.exists():
        print(f"Missing {mf}")
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    hashes = set()
    # check possible structures
    docs = data.get("documents") or data.get("notices") or data.get("items") or data
    if isinstance(docs, dict):
        for k, v in docs.items():
            if isinstance(v, dict):
                h = v.get("sha256") or v.get("hash") or v.get("sha256_hash")
                if h: hashes.add(h)
    elif isinstance(docs, list):
        for v in docs:
            if isinstance(v, dict):
                h = v.get("sha256") or v.get("hash") or v.get("sha256_hash")
                if h: hashes.add(h)
    print(f"{mf}: {len(hashes)} hashes")
    all_hashes.update(hashes)

print(f"\nTotal unique hashes across all 8 prior manifests: {len(all_hashes)}")
