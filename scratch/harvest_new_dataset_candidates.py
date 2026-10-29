import sqlite3
import json
import hashlib
from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher

# Load existing hashes
with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r") as f:
    frozen_manifest = json.load(f)
frozen_hashes = {d["sha256"] for d in frozen_manifest["documents"].values()}

with open("DEVELOPMENT_SET_MANIFEST.json", "r") as f:
    dev_manifest = json.load(f)
dev_hashes = {d["sha256"] for d in dev_manifest["documents"].values()}

existing_hashes = frozen_hashes.union(dev_hashes)
print(f"Total existing restricted hashes: {len(existing_hashes)}")

db = sqlite3.connect("data/testkart.db")
db.row_factory = sqlite3.Row

# Let's inspect unique URLs for each authority
for auth in ["Tamil Nadu Public Service Commission", "National Testing Agency", "Union Public Service Commission", "Staff Selection Commission", "Uttar Pradesh Public Service Commission"]:
    rows = db.execute("SELECT id, title, normalized_url, category FROM canonical_notices WHERE authority_name = ?", (auth,)).fetchall()
    print(f"\n{auth}: {len(rows)} canonical records in DB")
    # Show first 8 distinct URLs
    seen = set()
    sample = []
    for r in rows:
        url = r["normalized_url"]
        if url not in seen:
            seen.add(url)
            sample.append(r)
    print(f"Distinct URLs count: {len(seen)}")
    for r in sample[:6]:
        print(f"  - {r['title'][:40]} | {r['normalized_url']}")
