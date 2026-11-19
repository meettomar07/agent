import sqlite3

conn = sqlite3.connect('data/real_world_pilot_30day.db')
c = conn.cursor()

notices = c.execute('SELECT COUNT(*) FROM canonical_notices').fetchone()[0]
distinct_notices_with_facts = c.execute('''
    SELECT COUNT(DISTINCT nv.notice_id)
    FROM extracted_facts ef
    JOIN notice_versions nv ON ef.notice_version_id = nv.id
''').fetchone()[0]
total_facts = c.execute('SELECT COUNT(*) FROM extracted_facts').fetchone()[0]
articles = c.execute('SELECT COUNT(*) FROM blog_articles').fetchone()[0]
passed = c.execute("SELECT COUNT(*) FROM blog_articles WHERE status = 'QA_PASSED'").fetchone()[0]

print("=" * 65)
print(f"DATABASE RECRUITMENT STATUS:")
print(f"Total Canonical Notices:           {notices}")
print(f"Notices with Complete Facts:       {distinct_notices_with_facts} / {notices} ({(distinct_notices_with_facts/notices*100):.1f}%)")
print(f"Total Extracted Facts Saved:       {total_facts}")
print(f"Total Editorial Articles Created:  {articles} / {notices}")
print(f"QA Passed Articles:                {passed} / {articles} ({(passed/articles*100):.1f}%)")
print("=" * 65)

print("\nRecruitment Notices by Official Source:")
for r in c.execute('''
    SELECT s.code, s.name, COUNT(n.id)
    FROM canonical_notices n
    JOIN official_sources s ON n.source_id = s.id
    GROUP BY s.code
    ORDER BY COUNT(n.id) DESC
''').fetchall():
    print(f"  [{r[0]}] {r[1]}: {r[2]} notices")

print("\nNotice Versions by Source:")
for r in c.execute('''
    SELECT s.code, COUNT(nv.id)
    FROM notice_versions nv
    JOIN canonical_notices n ON nv.notice_id = n.id
    JOIN official_sources s ON n.source_id = s.id
    GROUP BY s.code
    ORDER BY COUNT(nv.id) DESC
''').fetchall():
    print(f"  [{r[0]}] {r[1]} versions")

conn.close()
