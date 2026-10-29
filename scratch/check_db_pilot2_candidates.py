import json
import sqlite3
from pathlib import Path

# Load all 145 hashes from the 6 manifests
manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json",
]
all_manifest_hashes = set()
all_manifest_urls = set()
all_manifest_titles = set()

for mf in manifest_files:
    data = json.loads(Path(mf).read_text(encoding="utf-8"))
    for k, doc in data.get("documents", {}).items():
        if "sha256" in doc and doc["sha256"]:
            all_manifest_hashes.add(doc["sha256"].lower().strip())
        if "source_url" in doc and doc["source_url"]:
            all_manifest_urls.add(doc["source_url"].lower().strip())
        if "title" in doc and doc["title"]:
            all_manifest_titles.add(doc["title"].lower().strip())

print(f"Loaded {len(all_manifest_hashes)} hashes, {len(all_manifest_urls)} URLs, {len(all_manifest_titles)} titles from 6 manifests.")

conn = sqlite3.connect("data/testkart.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT id, source_id, authority_name, title, normalized_url, category, state, published_date
    FROM canonical_notices
    ORDER BY published_date DESC, id DESC
""").fetchall()

print(f"Total canonical notices in DB: {len(rows)}")

cands_by_source = {}
for r in rows:
    u = (r["normalized_url"] or "").lower().strip()
    t = (r["title"] or "").lower().strip()
    if u in all_manifest_urls or t in all_manifest_titles:
        continue
    cands_by_source.setdefault(r["source_id"], []).append(r)

for s, items in cands_by_source.items():
    print(f"Source {s}: {len(items)} candidate notices")
    for it in items[:2]:
        print(f"   [{it['id']}] {it['title'][:80]} | {it['normalized_url'][:70]}")
