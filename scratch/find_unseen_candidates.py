import json
import sqlite3
import hashlib
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

print(f"Total frozen hashes collected: {len(frozen_hashes)}")

conn = sqlite3.connect("data/testkart.db")
cur = conn.cursor()
rows = cur.execute("""
    SELECT cn.id, cn.authority_name, cn.title, cn.category, nv.document_hash, nv.storage_path, nv.document_type
    FROM canonical_notices cn
    JOIN notice_versions nv ON cn.id = nv.notice_id
""").fetchall()
print(f"Total notice versions in db: {len(rows)}")

unseen_candidates = []
seen_hashes = set(frozen_hashes)

for r in rows:
    nid, auth, title, cat, dhash, spath, dtype = r
    if not dhash or dhash.lower() in seen_hashes:
        continue
    # Check if file actually exists on disk
    if spath and Path(spath).exists():
        file_bytes = Path(spath).read_bytes()
        actual_hash = hashlib.sha256(file_bytes).hexdigest().lower()
        if actual_hash in seen_hashes:
            continue
        seen_hashes.add(actual_hash)
        unseen_candidates.append({
            "id": nid,
            "authority": auth,
            "title": title,
            "category": cat,
            "hash": actual_hash,
            "path": spath,
            "type": dtype,
            "size": len(file_bytes)
        })

print(f"Unseen candidates with files on disk: {len(unseen_candidates)}")
for c in unseen_candidates[:20]:
    print(f"  [{c['id']}] {c['authority']} | {c['category']} | {c['title'][:60]} | {c['type']} | {c['size']} bytes")
