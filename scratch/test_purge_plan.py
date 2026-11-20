import sqlite3
from datetime import date, datetime
import re

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

today = date(2026, 11, 16)

# 1. Identify all notices that are clearly expired
# A notice is expired if:
# - recency_status == 'HISTORICAL' or 'EXPIRED'
# - It is not_f4c5077ef98a (ended 21 Oct 2026)
# - application_end_date is set and < 2026-11-16
# - title/url is from 2025/2024/2023/2022/2021/2020 exam cycles

rows = conn.execute("SELECT id, title, normalized_url, published_date, application_start_date, application_end_date, recency_status, first_discovered_at FROM canonical_notices").fetchall()

to_delete_ids = set()
to_keep_ids = set()

for r in rows:
    nid = r["id"]
    title = r["title"]
    url = r["normalized_url"]
    rec = r["recency_status"]
    end_str = r["application_end_date"]
    
    # Specific known expired notice currently viewed
    if nid == "not_f4c5077ef98a":
        to_delete_ids.add(nid)
        continue

    # Keep active known live notices
    if nid in ("not_ad71f5a41396", "not_a64a38fd6960", "not_c3f87ae192b2", "not_489c4fee4c59", "not_fa52f955a289", "not_7a854025059a"):
        to_keep_ids.add(nid)
        continue

    # Application end date in the past
    if end_str and re.match(r"^\d{4}-\d{2}-\d{2}$", end_str):
        try:
            end_d = datetime.strptime(end_str, "%Y-%m-%d").date()
            if end_d < today:
                to_delete_ids.add(nid)
                continue
            else:
                to_keep_ids.add(nid)
                continue
        except Exception:
            pass

    # Historical or expired status
    if rec in ("HISTORICAL", "EXPIRED"):
        to_delete_ids.add(nid)
        continue

    # Past years in title (2025 or earlier without 2026/2027)
    if re.search(r"\b(2025|2024|2023|2022|2021|2020)\b", title) and not ("2026" in title or "2027" in title):
        to_delete_ids.add(nid)
        continue

    # Auxiliary HTML portal links that are not actual notices
    if url and not (url.endswith(".pdf") or "pdf" in url.lower() or "/Download/" in url or "/whats-new/" in url or "/attachment/" in url or "/Document/" in url):
        # Generic portal anchors
        if any(w in title.lower() for w in ("apply online", "view all", "know more", "latest result", "our services", "welcome", "tenders", "contact us")):
            to_delete_ids.add(nid)
            continue

    to_keep_ids.add(nid)

print(f"Total evaluated: {len(rows)}")
print(f"To delete (Expired/Historical/Dead): {len(to_delete_ids)}")
print(f"To keep (Live/Active): {len(to_keep_ids)}")
