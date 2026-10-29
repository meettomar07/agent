import sqlite3

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

print("=== Existing blog_articles ===")
rows = c.execute("SELECT id, canonical_notice_id, template_type, current_version_id, status, title FROM blog_articles").fetchall()
for r in rows:
    print(r)
