import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

n = conn.execute("""
    SELECT cn.id, cn.authority_name, cn.title, cn.normalized_url, cn.status
    FROM canonical_notices cn
    WHERE cn.id NOT IN (SELECT canonical_notice_id FROM blog_articles)
""").fetchall()

print(f"Notices without blog articles: {len(n)}")
for r in n:
    print(dict(r))
