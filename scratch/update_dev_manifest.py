import hashlib
import json
from pathlib import Path

dev_dir = Path("data/development_notices")
dev_files = sorted(list(dev_dir.glob("dev_*")))

manifest = {
    "dataset_name": "DEVELOPMENT_SET_13_NOTICES",
    "purpose": "RULE_DEBUGGING_AND_DEVELOPMENT",
    "total_documents": len(dev_files),
    "documents": {},
}

for f in dev_files:
    content = f.read_bytes()
    manifest["documents"][f.name] = {
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }

with open("DEVELOPMENT_SET_MANIFEST.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Saved DEVELOPMENT_SET_MANIFEST.json with {len(dev_files)} files.")
