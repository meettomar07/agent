import sqlite3
import json
from pathlib import Path

# Check existing frozen validation filenames and hashes
with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r") as f:
    frozen_manifest = json.load(f)
frozen_hashes = set(doc["sha256"] for doc in frozen_manifest["documents"].values())
print(f"Frozen held-out hashes: {len(frozen_hashes)}")

# Check dev set hashes
with open("DEVELOPMENT_SET_MANIFEST.json", "r") as f:
    dev_manifest = json.load(f)
dev_hashes = set(item["sha256"] for item in dev_manifest["documents"].values())
print(f"Development set hashes: {len(dev_hashes)}")

doc_dir = Path("data/documents")
files = list(doc_dir.glob("*"))
print(f"Total files in data/documents: {len(files)}")

# Find documents in data/documents that are NEITHER frozen NOR dev
available_docs = []
for p in files:
    h = p.stem
    if h not in frozen_hashes and h not in dev_hashes:
        available_docs.append(p)

print(f"Available distinct documents in data/documents: {len(available_docs)}")

# Let's inspect authorities and formats for these documents via database notice_versions
db = sqlite3.connect("data/testkart.db")
db.row_factory = sqlite3.Row

auth_counts = {}
for p in available_docs:
    h = p.stem
    row = db.execute("""
        SELECT nv.document_type, cn.authority_name, cn.title, cn.category
        FROM notice_versions nv
        JOIN canonical_notices cn ON nv.notice_id = cn.id
        WHERE nv.document_hash = ?
    """, (h,)).fetchone()
    if row:
        auth = row["authority_name"]
        auth_counts[auth] = auth_counts.get(auth, 0) + 1

print("\nAvailable documents breakdown by authority in DB:")
for auth, cnt in sorted(auth_counts.items(), key=lambda x: -x[1]):
    print(f"  {auth}: {cnt}")
