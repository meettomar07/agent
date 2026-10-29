import json
import sqlite3
from pathlib import Path

# Load existing restricted
manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json",
]
restricted_hashes = set()
restricted_urls = set()
restricted_titles = set()

for mf in manifest_files:
    data = json.loads(Path(mf).read_text(encoding="utf-8"))
    for k, doc in data.get("documents", {}).items():
        if "sha256" in doc and doc["sha256"]:
            restricted_hashes.add(doc["sha256"].lower().strip())
        if "source_url" in doc and doc["source_url"]:
            restricted_urls.add(doc["source_url"].lower().strip())
        if "title" in doc and doc["title"]:
            restricted_titles.add(doc["title"].lower().strip())

conn = sqlite3.connect("data/testkart.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT id, authority_name, title, normalized_url, category, published_date
    FROM canonical_notices
    WHERE source_id = 'src_nta'
    ORDER BY published_date DESC
""").fetchall()

nta_cands = []
for r in rows:
    u = (r["normalized_url"] or "").lower().strip()
    t = (r["title"] or "").lower().strip()
    if u in restricted_urls or t in restricted_titles:
        continue
    nta_cands.append(r)

print(f"Total fresh NTA candidates in DB: {len(nta_cands)}")
for c in nta_cands[:10]:
    print("  ", c["title"][:70], "|", c["normalized_url"][:60])
