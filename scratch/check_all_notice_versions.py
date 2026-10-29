import sqlite3

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

rows = c.execute("SELECT nv.id, nv.notice_id, cn.authority_name, cn.title, cn.classification, cn.recency_status, length(nv.raw_text) FROM notice_versions nv JOIN canonical_notices cn ON nv.notice_id = cn.id").fetchall()
for r in rows:
    print(r)
