import sqlite3
from datetime import date, datetime
import re

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

# Get all live candidates
rows = conn.execute("SELECT id, authority_name, title, normalized_url, category, state, published_date, application_start_date, application_end_date, recency_status FROM canonical_notices WHERE recency_status NOT IN ('HISTORICAL', 'EXPIRED') AND id != 'not_f4c5077ef98a'").fetchall()

print(f"Total live candidates: {len(rows)}")

pdf_count = 0
html_count = 0
authorities = {}

for r in rows:
    auth = r["authority_name"]
    authorities[auth] = authorities.get(auth, 0) + 1
    if r["normalized_url"] and (r["normalized_url"].endswith(".pdf") or "pdf" in r["normalized_url"].lower()):
        pdf_count += 1
    else:
        html_count += 1

print(f"PDFs: {pdf_count}, HTML/Pages: {html_count}")
print("Authority breakdown:")
for a, c in sorted(authorities.items(), key=lambda x: -x[1]):
    print(f"  - {a}: {c}")

print("\nSample top recent PDF recruitments/notices:")
pdf_notices = [r for r in rows if r["normalized_url"] and (r["normalized_url"].endswith(".pdf") or "pdf" in r["normalized_url"].lower())]
for r in pdf_notices[:15]:
    print(f"  [{r['id']}] ({r['authority_name']}) {r['title'][:60]} | URL: {r['normalized_url'][:60]}")
