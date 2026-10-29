import sqlite3
import os
from pathlib import Path
import pymupdf

docs_dir = Path("data/documents")
conn = sqlite3.connect("data/testkart.db")
c = conn.cursor()

# Map documents to canonical_notices if possible
# Let's inspect notice_versions, canonical_notices, and unindexed PDFs in data/documents
all_docs = list(docs_dir.iterdir())
print(f"Total documents on disk: {len(all_docs)}")

# Let's look at notice_versions
nv_map = {}
for r in c.execute("SELECT nv.document_hash, nv.id, nv.notice_id, cn.authority_name, cn.title, cn.classification, cn.recency_status FROM notice_versions nv JOIN canonical_notices cn ON nv.notice_id = cn.id").fetchall():
    nv_map[r[0]] = {
        "nv_id": r[1],
        "notice_id": r[2],
        "authority": r[3],
        "title": r[4],
        "classification": r[5],
        "recency": r[6],
    }

print(f"Direct notice_versions mapped: {len(nv_map)}")
for h, d in list(nv_map.items())[:10]:
    print(f"  {h[:12]}: {d['authority']} | {d['classification']} | {d['title'][:60]}")
