import sqlite3
from pathlib import Path

conn = sqlite3.connect("data/testkart.db")
c = conn.cursor()

print("Notice versions count:", c.execute("SELECT count(*) FROM notice_versions").fetchone()[0])
print("Canonical notices count:", c.execute("SELECT count(*) FROM canonical_notices").fetchone()[0])

# Match files by sha256
docs_dir = Path("data/documents")
matched = 0
for f in docs_dir.iterdir():
    stem = f.stem  # usually sha256
    row = c.execute("SELECT id FROM notice_versions WHERE document_hash = ?", (stem,)).fetchone()
    if row:
        matched += 1
print(f"Files directly in notice_versions: {matched}")

# Also check how many canonical_notices have document URLs that could match
print("\nCanonical notices by authority:")
for r in c.execute("SELECT authority_name, count(*) FROM canonical_notices GROUP BY authority_name").fetchall():
    print(r)
