import sqlite3

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

print("=== Canonical notices status counts ===")
for r in c.execute("SELECT status, count(*) FROM canonical_notices GROUP BY status").fetchall():
    print(r)

print("\n=== Notices with notice_versions ===")
rows = c.execute("""
    SELECT cn.id, cn.authority_name, cn.title, cn.classification, cn.recency_status, nv.id, nv.version_number, length(nv.raw_text),
           (SELECT COUNT(*) FROM extracted_facts ef WHERE ef.notice_version_id = nv.id) as fact_count,
           (SELECT COUNT(*) FROM blog_articles ba WHERE ba.canonical_notice_id = cn.id) as art_count
    FROM canonical_notices cn
    JOIN notice_versions nv ON cn.id = nv.notice_id
""").fetchall()

for r in rows:
    print(r)
