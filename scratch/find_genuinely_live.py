import sqlite3
from datetime import date
import re

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT id, authority_name, title, normalized_url, category, state, classification, published_date, application_start_date, application_end_date, recency_status FROM canonical_notices").fetchall()

genuinely_live = []
expired_or_old = []

for r in rows:
    nid = r["id"]
    title = r["title"]
    url = r["normalized_url"]
    
    # Specific known live ones
    if nid in ("not_ad71f5a41396", "not_a64a38fd6960", "not_c3f87ae192b2", "not_489c4fee4c59", "not_fa52f955a289", "not_7a854025059a", "not_f04aec4e88c6"):
        genuinely_live.append(r)
        continue

    # Notice user flagged as expired
    if nid == "not_f4c5077ef98a":
        expired_or_old.append(r)
        continue

    # Old years in URL or title: 2012..2025
    if re.search(r"\b(201[0-9]|202[0-5])\b", url) or re.search(r"\b(201[0-9]|202[0-5])\b", title):
        # Unless it specifically has 2026 or 2027 in title
        if not ("2026" in title or "2027" in title):
            expired_or_old.append(r)
            continue

    # If marked HISTORICAL or EXPIRED
    if r["recency_status"] in ("HISTORICAL", "EXPIRED"):
        expired_or_old.append(r)
        continue

    # Generic HTML portal buttons/links
    if any(w in title.lower() for w in ("apply online", "view all", "know more", "latest result", "our services", "welcome", "tenders", "contact us", "sitemap", "guidelines", "regional office")):
        expired_or_old.append(r)
        continue

    # If non-English Kannada navigation titles without 2026/2027
    if not re.search(r"[a-zA-Z]", title):
        if not ("2026" in title or "2027" in title):
            expired_or_old.append(r)
            continue

    genuinely_live.append(r)

print(f"Genuinely Live / Active 2026-2027 notices: {len(genuinely_live)}")
print(f"Expired / Historical / Auxiliary to remove: {len(expired_or_old)}")
print("\nActive Live Opportunities:")
for r in genuinely_live[:20]:
    print(f"  [{r['id']}] ({r['authority_name']}) {r['title'][:60]}")
