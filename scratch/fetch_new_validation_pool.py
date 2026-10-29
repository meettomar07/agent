import hashlib
import json
from pathlib import Path
import sqlite3
import time
from testkart_intelligence.discovery.fetcher import SafeFetcher

# Load existing hashes to ensure 0 overlap
with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r") as f:
    frozen_manifest = json.load(f)
frozen_hashes = {d["sha256"] for d in frozen_manifest["documents"].values()}

with open("DEVELOPMENT_SET_MANIFEST.json", "r") as f:
    dev_manifest = json.load(f)
dev_hashes = {d["sha256"] for d in dev_manifest["documents"].values()}

restricted_hashes = frozen_hashes.union(dev_hashes)
print(f"Restricted hashes (frozen + dev): {len(restricted_hashes)}")

out_dir = Path("data/new_validation_notices")
out_dir.mkdir(parents=True, exist_ok=True)

fetcher = SafeFetcher()
db = sqlite3.connect("data/testkart.db")
db.row_factory = sqlite3.Row

# Get TNPSC candidate URLs
tnpsc_rows = db.execute("SELECT id, title, normalized_url, category FROM canonical_notices WHERE authority_name = 'Tamil Nadu Public Service Commission'").fetchall()

# Get NTA candidate URLs
nta_rows = db.execute("SELECT id, title, normalized_url, category FROM canonical_notices WHERE authority_name = 'National Testing Agency'").fetchall()

# Get UPSC candidate URLs
upsc_rows = db.execute("SELECT id, title, normalized_url, category FROM canonical_notices WHERE authority_name = 'Union Public Service Commission'").fetchall()

print(f"Candidate pools: TNPSC={len(tnpsc_rows)}, NTA={len(nta_rows)}, UPSC={len(upsc_rows)}")
