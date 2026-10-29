import sqlite3

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

print("=== Blog Articles in testkart.db ===")
for r in c.execute("SELECT ba.id, ba.canonical_notice_id, ba.template_type, ba.status, ba.title, av.version_number FROM blog_articles ba JOIN article_versions av ON ba.current_version_id = av.id").fetchall():
    print(r)

print("\n=== Recent Audit Events ===")
for r in c.execute("SELECT id, entity_type, entity_id, action, actor, timestamp FROM audit_events ORDER BY timestamp DESC LIMIT 10").fetchall():
    print(r)
