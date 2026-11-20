import sqlite3
import re
from collections import Counter

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

notices = conn.execute("SELECT id, authority_name, title, normalized_url FROM canonical_notices").fetchall()

year_counter = Counter()
by_authority = Counter()
old_notices = []

for n in notices:
    title = n["title"]
    url = n["normalized_url"]
    combined = title + " " + url
    
    # Extract years (4 digits)
    years = [int(y) for y in re.findall(r'\b(19\d\d|20[0-3]\d)\b', combined)]
    # Filter reasonable years
    years = [y for y in years if 1990 <= y <= 2030]
    
    if years:
        max_year = max(years)
        year_counter[max_year] += 1
        if max_year < 2025:
            old_notices.append((n["id"], n["authority_name"], title, max_year, url))
    else:
        year_counter["No Year in Title/URL"] += 1
        
    by_authority[n["authority_name"]] += 1

print("=== Notices by Year Detected ===")
for yr, cnt in sorted(year_counter.items(), key=lambda x: str(x[0])):
    print(f"Year {yr}: {cnt} notices")

print(f"\nTotal historical notices strictly < 2025: {len(old_notices)}")
print("\nSample of historical notices still present:")
for nid, auth, t, yr, u in old_notices[:20]:
    print(f"[{yr}] [{auth}] {t[:60]} | {u[:60]}")
