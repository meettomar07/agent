import sqlite3

conn = sqlite3.connect('data/real_world_pilot_30day.db')
c = conn.cursor()

print("APPSC_AR Notices and their version status:")
rows = c.execute("""
    SELECT cn.id, cn.status, cn.title, nv.id as version_id
    FROM canonical_notices cn
    LEFT JOIN notice_versions nv ON cn.id = nv.notice_id
    WHERE cn.source_id = 'src_appsc_ar'
    ORDER BY cn.first_discovered_at ASC
""").fetchall()

for idx, r in enumerate(rows, 1):
    status = "HAS_VERSION" if r[3] else "NO_VERSION"
    print(f"[{idx:02d}] {r[0]} | NoticeStatus: {r[1]} | {status} | {r[2][:50]}")

conn.close()
