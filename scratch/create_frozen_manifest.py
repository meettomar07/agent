import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, ".")

from scratch.run_held_out_evaluation_33 import GROUND_TRUTH

val_dir = Path("data/validation_notices")
manifest = {
    "dataset_name": "FROZEN_HELD_OUT_33_EVALUATION_DATASET",
    "created_at": "2026-10-27T13:30:00Z",
    "status": "FROZEN_INDEPENDENT_EVALUATION_BENCHMARK",
    "total_documents": len(GROUND_TRUTH),
    "documents": {},
}

for fname, meta in GROUND_TRUTH.items():
    p = val_dir / fname
    content = p.read_bytes()
    h = hashlib.sha256(content).hexdigest()
    manifest["documents"][fname] = {
        "sha256": h,
        "size_bytes": len(content),
        "authority": meta["authority"],
        "category": meta["category"],
        "format": meta["format"],
        "readable": meta["readable"],
        "ground_truth_facts": meta["facts"],
    }

manifest_path = Path("FROZEN_HELD_OUT_DATASET_MANIFEST.json")
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Created {manifest_path} with {len(manifest['documents'])} frozen documents.")
