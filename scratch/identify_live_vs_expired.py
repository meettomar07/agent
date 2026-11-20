import sqlite3
from datetime import date, datetime
import re

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

today = date(2026, 11, 16)

# 1. First, check not_f4c5077ef98a
r = conn.execute("SELECT id, title, normalized_url, application_end_date, recency_status FROM canonical_notices WHERE id = 'not_f4c5077ef98a'").fetchone()
if r:
    print(f"Target notice: {dict(r)}")

# Find all notices with deadlines or dates
rows = conn.execute("SELECT id, title, normalized_url, category, state, published_date, application_start_date, application_end_date, recency_status, first_discovered_at FROM canonical_notices").fetchall()

expired_ids = []
live_candidates = []

for r in rows:
    nid = r["id"]
    title = r["title"]
    url = r["normalized_url"]
    rec = r["recency_status"]
    end_str = r["application_end_date"]
    pub_str = r["published_date"]
    
    # Explicitly expired notice
    if nid == "not_f4c5077ef98a":
        expired_ids.append((nid, "Indian Coast Guard CGEPT (Ended 21 Oct 2026)"))
        continue
        
    # Expired by recency_status
    if rec in ("HISTORICAL", "EXPIRED"):
        expired_ids.append((nid, f"Marked {rec}"))
        continue
        
    # Expired by application_end_date
    if end_str and re.match(r"^\d{4}-\d{2}-\d{2}$", end_str):
        try:
            end_d = datetime.strptime(end_str, "%Y-%m-%d").date()
            if end_d < today:
                expired_ids.append((nid, f"End date past: {end_str}"))
                continue
            else:
                live_candidates.append(r)
                continue
        except Exception:
            pass
            
    # Check if title or url has historical year (2025, 2024, 2023, 2022)
    if re.search(r"\b(2025|2024|2023|2022|2021|2020|2019)\b", title) and not ("2026" in title or "2027" in title):
        expired_ids.append((nid, "Historical year in title"))
        continue

    # Discovered recently (November 2026) or ongoing
    live_candidates.append(r)

print(f"Total notices: {len(rows)}")
print(f"Expired/Passed away to remove: {len(expired_ids)}")
print(f"Live/Active candidates remaining: {len(live_candidates)}")
