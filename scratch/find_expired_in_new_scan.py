import sqlite3
import re

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

notices = c.execute("SELECT id, title, authority_name, status, normalized_url FROM canonical_notices WHERE status != 'QA_PASSED'").fetchall()
print(f"Total non-QA_PASSED notices: {len(notices)}")

expired_ids = []
current_year = 2026

for n in notices:
    title = n["title"]
    # Check for past years (e.g. 2009-2024 or 2025 with past dates)
    years = [int(y) for y in re.findall(r'\b(20[0-2][0-5])\b', title)]
    # Also check if title contains 2009, 2010, etc.
    old_years = [int(y) for y in re.findall(r'\b(19\d\d|200\d)\b', title)]
    
    if years or old_years:
        # If it explicitly references only past years (e.g. 2012, 2014, 2020) and not 2026/2027
        has_current_or_future = bool(re.search(r'\b(2026|2027|2028)\b', title))
        if not has_current_or_future:
            expired_ids.append((n["id"], n["authority_name"], title[:70]))

print(f"Detected {len(expired_ids)} historical/expired notices from past years:")
for eid, auth, t in expired_ids[:15]:
    print(f" - [{auth}] {t}")
