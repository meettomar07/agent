import sqlite3
import os
from pathlib import Path

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

# Check all notices in canonical_notices with their urls and see if any PDF in data/documents matches
files = os.listdir('data/documents')
print(f"Total files in data/documents: {len(files)}")

# Check canonical_notices
notices = c.execute("SELECT id, source_id, title, classification, recency_status, normalized_url FROM canonical_notices WHERE id IN ('not_9b1eef28c437', 'not_f00428943a2e', 'not_57fca6f9a1c9', 'not_d45c05a3f2ae', 'not_c2d5f50c09b8', 'not_2db460a18bee', 'not_99f6cc7df5b8')").fetchall()
for n in notices:
    print(n)
