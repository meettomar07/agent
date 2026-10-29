import sqlite3

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

r = c.execute("SELECT * FROM canonical_notices WHERE id = 'not_9b1eef28c437'").fetchone()
print("Cancellation notice:", r)

# Check if there are other cancellation notices in canonical_notices
cancels = c.execute("SELECT id, source_id, authority_name, title, classification, normalized_url FROM canonical_notices WHERE classification = 'CANCELLATION_NOTICE'").fetchall()
print("\nAll CANCELLATION_NOTICE:", cancels)
