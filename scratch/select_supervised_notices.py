import sqlite3

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

print("=== Recruitment notifications ===")
rows = c.execute("SELECT id, source_id, title, classification, recency_status, normalized_url FROM canonical_notices WHERE classification = 'RECRUITMENT_NOTIFICATION' LIMIT 10").fetchall()
for r in rows:
    print(r)

print("\n=== Current notices ===")
rows = c.execute("SELECT id, source_id, title, classification, recency_status, normalized_url FROM canonical_notices WHERE recency_status = 'CURRENT' LIMIT 10").fetchall()
for r in rows:
    print(r)
