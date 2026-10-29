import sqlite3
import json
from pathlib import Path

# Collect all 119 frozen sha256 hashes
frozen_hashes = set()
for manifest_name in [
    "DEVELOPMENT_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json"
]:
    with open(manifest_name, encoding="utf-8") as f:
        m = json.load(f)
        for doc_name, meta in m["documents"].items():
            h = meta.get("sha256")
            if h:
                frozen_hashes.add(h.lower())

print(f"Total frozen hashes: {len(frozen_hashes)}")

conn = sqlite3.connect("data/testkart.db")
cur = conn.cursor()

# Get TNPSC notices
tnpsc_rows = cur.execute("""
    SELECT authority_name, title, normalized_url, category
    FROM canonical_notices
    WHERE authority_name LIKE '%Tamil Nadu%'
    ORDER BY id DESC
    LIMIT 40
""").fetchall()

print(f"\nTNPSC candidate sample ({len(tnpsc_rows)}):")
for r in tnpsc_rows[:10]:
    print(" ", r)

# Get NTA notices
nta_rows = cur.execute("""
    SELECT authority_name, title, normalized_url, category
    FROM canonical_notices
    WHERE authority_name LIKE '%National Testing%' AND normalized_url LIKE '%.pdf'
    ORDER BY id DESC
    LIMIT 20
""").fetchall()

print(f"\nNTA candidate sample ({len(nta_rows)}):")
for r in nta_rows[:10]:
    print(" ", r)

# Get UPSC notices
upsc_rows = cur.execute("""
    SELECT authority_name, title, normalized_url, category
    FROM canonical_notices
    WHERE authority_name LIKE '%Union Public%'
    ORDER BY id DESC
    LIMIT 20
""").fetchall()

print(f"\nUPSC candidate sample ({len(upsc_rows)}):")
for r in upsc_rows[:10]:
    print(" ", r)
