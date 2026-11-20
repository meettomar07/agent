import sqlite3
from testkart_intelligence.config import settings

conn = sqlite3.connect(settings.DATABASE_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, title, normalized_url, status FROM canonical_notices WHERE status = 'DISCOVERED'").fetchall()
print(f"Total DISCOVERED notices: {len(rows)}")
for r in rows:
    v_count = conn.execute("SELECT count(*) as c FROM notice_versions WHERE notice_id = ?", (r["id"],)).fetchone()["c"]
    print(f"- {r['id']} | Versions: {v_count} | {r['title'][:50]} | {r['normalized_url']}")
