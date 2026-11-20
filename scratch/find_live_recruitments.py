import sqlite3

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

# Get genuinely live notices
with open('scratch/find_genuinely_live.py') as f:
    code = f.read()
scope = {}
exec(code, scope)
live = scope['genuinely_live']

recruitment_notices = []
for r in live:
    cat = r["classification"]
    title = r["title"].lower()
    if cat == "RECRUITMENT_NOTIFICATION" or any(w in title for w in ("recruitment", "posts", "vacancies", "examination", "junior engineer", "constable", "sub-inspector", "shreshta", "officer", "cgl", "chsl")):
        recruitment_notices.append(r)

print(f"Total live recruitment notices: {len(recruitment_notices)}")
for r in recruitment_notices[:25]:
    print(f"  [{r['id']}] ({r['authority_name']}) {r['title'][:60]}")
