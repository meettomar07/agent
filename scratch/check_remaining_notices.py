import sqlite3
from datetime import date, datetime
import re

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

today = date(2026, 11, 16)

# Check all notices that were discovered recently (in November 2026)
rows = conn.execute("SELECT id, title, normalized_url, published_date, application_start_date, application_end_date, recency_status, first_discovered_at FROM canonical_notices WHERE recency_status NOT IN ('HISTORICAL', 'EXPIRED')").fetchall()
print(f"Remaining non-historical/non-expired notices: {len(rows)}")

for r in rows[:30]:
    print(f"- {r['id']} | Recency: {r['recency_status']} | Discovered: {r['first_discovered_at'][:10]} | End: {r['application_end_date']} | Title: {r['title'][:55]}")
