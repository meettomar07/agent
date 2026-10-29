import sqlite3
import json
from pathlib import Path

db = sqlite3.connect("data/testkart.db")
db.row_factory = sqlite3.Row

# Load frozen held out hashes to ensure 0 overlap
with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r") as f:
    frozen_manifest = json.load(f)
frozen_hashes = {d["sha256"] for d in frozen_manifest["documents"].values()}

# Load dev manifest hashes to ensure 0 overlap
with open("DEVELOPMENT_SET_MANIFEST.json", "r") as f:
    dev_manifest = json.load(f)
dev_hashes = {d["sha256"] for d in dev_manifest["documents"].values()}

print(f"Frozen hashes count: {len(frozen_hashes)}")
print(f"Dev hashes count: {len(dev_hashes)}")

# Check canonical notices in DB
auths = db.execute("SELECT DISTINCT authority_name FROM canonical_notices").fetchall()
for a in auths:
    auth_name = a["authority_name"]
    cnt = db.execute("SELECT count(*) FROM canonical_notices WHERE authority_name = ?", (auth_name,)).fetchone()[0]
    print(f"\nAuthority: {auth_name} (Total canonical: {cnt})")
    rows = db.execute("SELECT id, title, normalized_url, category FROM canonical_notices WHERE authority_name = ? LIMIT 5", (auth_name,)).fetchall()
    for r in rows:
        print(f"  [{r['category']}] {r['title'][:60]} -> {r['normalized_url']}")
