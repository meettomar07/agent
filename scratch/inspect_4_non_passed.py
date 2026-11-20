import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT ba.id, ba.title, ba.status, ba.canonical_notice_id, cn.authority_name, cn.title as notice_title
    FROM blog_articles ba
    JOIN canonical_notices cn ON cn.id = ba.canonical_notice_id
    WHERE ba.status != 'QA_PASSED'
""").fetchall()

print(f"Non-QA_PASSED articles ({len(rows)}):")
for r in rows:
    print(f"[{r['status']}] [{r['authority_name']}] {r['title']}")
