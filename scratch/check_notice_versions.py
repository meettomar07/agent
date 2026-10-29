import sqlite3

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

print("=== notice_versions count ===")
print(c.execute("SELECT COUNT(*) FROM notice_versions").fetchone())

print("\n=== Sample notice_versions ===")
for r in c.execute("SELECT id, notice_id, version_number, document_type, length(raw_text), storage_path FROM notice_versions LIMIT 10").fetchall():
    print(r)
