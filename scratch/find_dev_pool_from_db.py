import sqlite3
import json
from pathlib import Path

with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
    manifest = json.load(f)

frozen_hashes = {doc["sha256"] for doc in manifest["documents"].values()}

conn = sqlite3.connect("data/testkart.db")
c = conn.cursor()

candidates = []
for auth in ["src_ssc", "src_upsc", "src_nta", "src_tnpsc"]:
    rows = c.execute("SELECT id, source_id, title, classification, normalized_url FROM canonical_notices WHERE source_id = ? LIMIT 30", (auth,)).fetchall()
    for r in rows:
        candidates.append(r)

print(f"Total candidate rows from canonical_notices: {len(candidates)}")
for r in candidates[:20]:
    print(f"[{r[1]}] [{r[3]}] {r[2][:50]} -> {r[4]}")
