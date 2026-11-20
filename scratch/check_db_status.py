import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

failed = c.execute("""
    SELECT qr.article_version_id, qr.passed, qr.score, qr.rule_name, qr.message, ba.title
    FROM qa_results qr
    JOIN article_versions av ON av.id = qr.article_version_id
    JOIN blog_articles ba ON ba.id = av.article_id
    WHERE qr.passed = 0
    ORDER BY qr.created_at DESC
    LIMIT 10
""").fetchall()

for f in failed:
    print("---")
    print("Title:", f["title"])
    print("Rule:", f["rule_name"], "| Score:", f["score"])
    print("Msg:", f["message"])
