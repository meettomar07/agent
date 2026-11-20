import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

art = conn.execute("""
    SELECT ba.id, ba.title, ba.status, ba.slug, cn.title as notice_title, cn.normalized_url
    FROM blog_articles ba
    JOIN canonical_notices cn ON cn.id = ba.canonical_notice_id
    WHERE cn.title LIKE '%APPSCCE%' OR cn.normalized_url LIKE '%APPSCCE%'
""").fetchall()

for a in art:
    print(dict(a))
