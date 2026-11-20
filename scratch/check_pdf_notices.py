import sqlite3

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, title, normalized_url, status FROM canonical_notices WHERE normalized_url LIKE '%.pdf' ORDER BY first_discovered_at DESC LIMIT 15").fetchall()
print(f"Total found: {len(rows)}")
for r in rows:
    v_count = conn.execute("SELECT count(*) as c FROM notice_versions WHERE notice_id = ?", (r["id"],)).fetchone()["c"]
    f_count = conn.execute("SELECT count(*) as c FROM extracted_facts WHERE notice_version_id IN (SELECT id FROM notice_versions WHERE notice_id = ?)", (r["id"],)).fetchone()["c"]
    print(f"ID: {r['id']} | Versions: {v_count} | Facts: {f_count} | Title: {r['title'][:45]} | URL: {r['normalized_url']}")
