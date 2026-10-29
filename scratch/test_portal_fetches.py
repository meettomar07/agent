import sqlite3
import hashlib
from testkart_intelligence.discovery.fetcher import SafeFetcher

fetcher = SafeFetcher()
db = sqlite3.connect("data/testkart.db")
db.row_factory = sqlite3.Row

# Test 5 TNPSC URLs
tnpsc_rows = db.execute("SELECT title, normalized_url FROM canonical_notices WHERE authority_name = 'Tamil Nadu Public Service Commission' LIMIT 5").fetchall()
print("Testing TNPSC fetches:")
for r in tnpsc_rows:
    url = r["normalized_url"]
    try:
        content, ctype, final_url, status = fetcher.fetch(url)
        print(f"  OK: {len(content)} bytes | {ctype} | {r['title'][:40]}")
    except Exception as e:
        print(f"  FAIL: {url} -> {e}")

# Test 5 NTA URLs
nta_rows = db.execute("SELECT title, normalized_url FROM canonical_notices WHERE authority_name = 'National Testing Agency' LIMIT 5").fetchall()
print("\nTesting NTA fetches:")
for r in nta_rows:
    url = r["normalized_url"]
    try:
        content, ctype, final_url, status = fetcher.fetch(url)
        print(f"  OK: {len(content)} bytes | {ctype} | {r['title'][:40]}")
    except Exception as e:
        print(f"  FAIL: {url} -> {e}")
