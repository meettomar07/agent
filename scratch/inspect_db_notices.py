import sqlite3

conn = sqlite3.connect("data/testkart.db")
conn.row_factory = sqlite3.Row

counts = conn.execute("""
    SELECT source_id, authority_name, count(*) as cnt
    FROM canonical_notices
    GROUP BY source_id, authority_name
""").fetchall()

for c in counts:
    print(f"{c['source_id']} ({c['authority_name']}): {c['cnt']} notices")
