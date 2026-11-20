import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT id, title, authority_name, status FROM canonical_notices WHERE status != 'QA_PASSED'").fetchall()
print(f"Remaining non-QA_PASSED: {len(rows)}")
for r in rows:
    print(f"[{r['status']}] [{r['authority_name']}] {r['title']}")
