import sqlite3
import json

with open('DEVELOPMENT_SET_MANIFEST.json') as f:
    dev = json.load(f)
dev_hashes = {d['sha256'] for d in dev['documents'].values()}
with open('NEW_VALIDATION_DATASET_MANIFEST.json') as f:
    val52 = json.load(f)
val52_hashes = {d['sha256'] for d in val52['documents'].values()}
with open('FROZEN_HELD_OUT_DATASET_MANIFEST.json') as f:
    val33 = json.load(f)
val33_hashes = {d['sha256'] for d in val33['documents'].values()}
all_existing = dev_hashes | val52_hashes | val33_hashes

conn = sqlite3.connect('data/testkart.db')
cur = conn.cursor()

rows = cur.execute('SELECT id, title, normalized_url, category FROM canonical_notices WHERE authority_name = ?', ('Tamil Nadu Public Service Commission',)).fetchall()

print(f"Total TNPSC rows: {len(rows)}")
for i, r in enumerate(rows):
    if any(k in r[1].lower() for k in ['recruitment', 'officer', 'assistant', 'inspector', 'engineer', 'examination', 'post']):
        print(f"{i}: [{r[0]}] {r[1]} -> {r[2]}")
