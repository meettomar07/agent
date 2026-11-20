import sqlite3
from datetime import date
import json

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

# Run purge test
with open('scratch/test_purge_plan.py') as f:
    code = f.read()
scope = {}
exec(code, scope)
to_keep_ids = scope['to_keep_ids']

print(f"Analyzing {len(to_keep_ids)} live notices...")

# Group by authority
by_auth = {}
for nid in to_keep_ids:
    row = conn.execute("SELECT * FROM canonical_notices WHERE id = ?", (nid,)).fetchone()
    auth = row["authority_name"]
    by_auth.setdefault(auth, []).append(row)

for auth, rows in by_auth.items():
    print(f"\nAuthority: {auth} ({len(rows)} live notices)")
    for r in rows[:5]:
        v_count = conn.execute("SELECT count(*) as c FROM notice_versions WHERE notice_id = ?", (r["id"],)).fetchone()["c"]
        f_count = conn.execute("SELECT count(*) as c FROM extracted_facts WHERE notice_version_id IN (SELECT id FROM notice_versions WHERE notice_id = ?)", (r["id"],)).fetchone()["c"]
        print(f"  - [{r['id']}] Versions: {v_count}, Facts: {f_count} | {r['title'][:55]} | {r['normalized_url'][:60]}")
