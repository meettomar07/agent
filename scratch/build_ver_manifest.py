import json
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, ".")
ver_dir = Path("data/verification_notices")
from scratch.evaluate_verification_set import VERIFICATION_GROUND_TRUTH

manifest = {
    "dataset_name": "INDEPENDENT_VERIFICATION_SET_11_NOTICES",
    "purpose": "GENERALIZATION_VERIFICATION_AFTER_FROZEN_REMEDIATION",
    "total_documents": len(VERIFICATION_GROUND_TRUTH),
    "documents": {}
}

for fname, meta in sorted(VERIFICATION_GROUND_TRUTH.items()):
    fpath = ver_dir / fname
    fb = fpath.read_bytes()
    chash = hashlib.sha256(fb).hexdigest().lower()
    manifest["documents"][fname] = {
        "sha256": chash,
        "size_bytes": len(fb),
        "authority": meta["authority"],
        "category": meta["category"],
        "format": meta["format"],
        "readable": meta["readable"],
        "ground_truth_facts": meta["facts"]
    }

manifest_path = Path("VERIFICATION_SET_MANIFEST.json")
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

manifest_bytes = manifest_path.read_bytes()
manifest_hash = hashlib.sha256(manifest_bytes).hexdigest().upper()

print(f"Generated {manifest_path} with {len(manifest['documents'])} documents.")
print(f"Manifest SHA-256: {manifest_hash}")
