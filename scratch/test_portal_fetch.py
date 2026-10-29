import sqlite3
from testkart_intelligence.discovery.fetcher import SafeFetcher

fetcher = SafeFetcher()
conn = sqlite3.connect('data/testkart.db')
cur = conn.cursor()

rows = cur.execute('SELECT authority_name, title, normalized_url FROM canonical_notices WHERE authority_name = ? LIMIT 5', ('Tamil Nadu Public Service Commission',)).fetchall()
for r in rows:
    print('Testing fetch:', r[1][:50], r[2])
    try:
        content, ctype, final_url, status = fetcher.fetch(r[2])
        print('  Status:', status, 'Content-Type:', ctype, 'Length:', len(content))
    except Exception as e:
        print('  Error:', e)
