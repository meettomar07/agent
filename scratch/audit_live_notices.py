import sqlite3
from datetime import date, datetime
import re

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

today = date(2026, 11, 16)
print(f"Auditing notices against today: {today}")

# Check notices with application_end_date
rows = conn.execute("SELECT id, title, normalized_url, application_start_date, application_end_date, recency_status FROM canonical_notices").fetchall()

live_notices = []
expired_notices = []

for r in rows:
    end_str = r["application_end_date"]
    title = r["title"]
    url = r["normalized_url"]
    
    # Check if end date is set and valid
    if end_str and re.match(r"^\d{4}-\d{2}-\d{2}$", end_str):
        try:
            end_d = datetime.strptime(end_str, "%Y-%m-%d").date()
            if end_d >= today:
                live_notices.append((r["id"], title, url, end_str, "END_DATE_FUTURE"))
                continue
            else:
                expired_notices.append((r["id"], title, url, end_str, "END_DATE_PAST"))
                continue
        except Exception:
            pass
            
    # Check if notice mentions dates in title or URL
    # If title mentions 2024 or 2025 or old exam cycles
    if re.search(r"\b(2024|2023|2022|2021|2020|2019|2018)\b", title):
        expired_notices.append((r["id"], title, url, None, "HISTORICAL_YEAR"))
        continue
        
    # Check if notice has recency_status HISTORICAL or EXPIRED
    if r["recency_status"] in ("HISTORICAL", "EXPIRED"):
        expired_notices.append((r["id"], title, url, None, f"STATUS_{r['recency_status']}"))
        continue

print(f"Total evaluated: {len(rows)}")
print(f"Live notices identified so far: {len(live_notices)}")
print(f"Expired/Historical notices identified: {len(expired_notices)}")

for n in live_notices[:10]:
    print(f"  LIVE: {n[0]} | {n[3]} | {n[1][:50]}")
