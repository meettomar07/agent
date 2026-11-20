import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT cn.id, cn.title, cn.normalized_url
    FROM canonical_notices cn
    WHERE cn.id IN (SELECT canonical_notice_id FROM blog_articles WHERE status != 'QA_PASSED')
""").fetchall()

for r in rows:
    print(r["id"], "|", r["title"], "|", r["normalized_url"])
