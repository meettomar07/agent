import sqlite3
import json

conn = sqlite3.connect('data/testkart.db')
cur = conn.cursor()

for auth in ['National Testing Agency', 'Staff Selection Commission', 'Union Public Service Commission', 'Uttar Pradesh Public Service Commission']:
    print(f'=== Authority: {auth} ===')
    rows = cur.execute(
        "SELECT notice_number, title, normalized_url, category FROM canonical_notices WHERE authority_name = ? LIMIT 20",
        (auth,)
    ).fetchall()
    for i, r in enumerate(rows):
        print(f"  {i+1}: {r[0]} | {r[1][:60]} | {r[2]}")
