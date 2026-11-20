import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, title, canonical_notice_id FROM blog_articles WHERE status = 'QA_FAILED'").fetchall()
for r in rows:
    print(r["id"], r["canonical_notice_id"], r["title"])
