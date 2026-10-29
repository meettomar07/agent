import json
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
all_urls = set()
all_titles = set()
total_docs = 0

for mf in manifest_files:
    p = Path(mf)
    if not p.exists():
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    docs = data.get("documents", {})
    print(f"{mf}: {len(docs)} documents")
    total_docs += len(docs)
    for k, doc in docs.items():
        if "sha256" in doc:
            all_hashes.add(doc["sha256"].lower())
        if "source_url" in doc:
            all_urls.add(doc["source_url"].strip().lower())
        if "title" in doc:
            all_titles.add(doc["title"].strip().lower())

print(f"Total across manifests: {total_docs}")
print(f"Unique sha256: {len(all_hashes)}")
print(f"Unique source URLs: {len(all_urls)}")
