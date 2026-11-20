import sqlite3
import re

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

notices = conn.execute("""
    SELECT cn.id, cn.authority_name, cn.title, cn.normalized_url,
           ba.id as article_id, ba.title as article_title
    FROM canonical_notices cn
    LEFT JOIN blog_articles ba ON ba.canonical_notice_id = cn.id
""").fetchall()

print(f"Total notices in DB: {len(notices)}")

# Categorize notices
historical = []
current_live = []

for n in notices:
    text = (n["title"] + " " + n["normalized_url"]).lower()
    
    # Check if there is an explicit past year strictly before 2025
    past_years = [int(y) for y in re.findall(r'\b(19\d\d|200\d|201\d|202[0-4])\b', text)]
    live_years = [int(y) for y in re.findall(r'\b(202[5-9]|203\d)\b', text)]
    
    if past_years and not live_years:
        historical.append(n)
    else:
        current_live.append(n)

print(f"Historical notices (< 2025): {len(historical)}")
print(f"Current / Live recruitment notices (>= 2025 or undated live): {len(current_live)}")

# Check duplicates among current_live
seen_titles = {}
live_dupes = []
for n in current_live:
    # Normalize title: remove punctuation, lowercase
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', n["title"].lower()).strip()
    # Key by authority + clean title
    key = (n["authority_name"], clean_title)
    if key in seen_titles:
        live_dupes.append((key, n, seen_titles[key]))
    else:
        seen_titles[key] = n

print(f"\nDuplicates among Current/Live notices: {len(live_dupes)}")
for key, n1, n2 in live_dupes:
    print(f" - [{key[0]}] '{key[1][:60]}'")
    print(f"     Notice 1: {n1['id']} | {n1['normalized_url'][:60]}")
    print(f"     Notice 2: {n2['id']} | {n2['normalized_url'][:60]}")
