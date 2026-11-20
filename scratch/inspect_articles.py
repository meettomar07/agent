import sqlite3

conn = sqlite3.connect('data/real_world_pilot_30day.db')
c = conn.cursor()

print("Status Breakdown in blog_articles:")
for r in c.execute("SELECT status, COUNT(*) FROM blog_articles GROUP BY status").fetchall():
    print(f"  {r[0]}: {r[1]}")

print("\nSample Non-QA_PASSED Articles (if any):")
for r in c.execute("""
    SELECT a.id, a.title, a.status, qr.score, qr.message
    FROM blog_articles a
    LEFT JOIN qa_results qr ON a.current_version_id = qr.article_version_id
    WHERE a.status != 'QA_PASSED'
    LIMIT 5
""").fetchall():
    print(f"  ID: {r[0]} | Status: {r[2]} | Score: {r[3]} | Msg: {r[4]}")

conn.close()
