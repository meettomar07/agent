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

for auth in ['Tamil Nadu Public Service Commission', 'Union Public Service Commission', 'Staff Selection Commission', 'Uttar Pradesh Public Service Commission', 'National Testing Agency']:
    rows = cur.execute('SELECT id, title, normalized_url, category FROM canonical_notices WHERE authority_name = ?', (auth,)).fetchall()
    print(f"\nAuthority: {auth} (Total rows in DB: {len(rows)})")
    # Show first 5 recruitment-related or interesting titles
    for r in rows[:8]:
        print(f"  [{r[0]}] {r[1][:60]} -> {r[2]}")
