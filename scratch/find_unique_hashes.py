import hashlib
from pathlib import Path
import sqlite3

val_dir = Path("data/validation_notices")
docs_dir = Path("data/documents")

# Get hashes of current validation notices
val_hashes = {}
for f in val_dir.glob("notice_*"):
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    if h not in val_hashes:
        val_hashes[h] = f.name
    else:
        print(f"Duplicate hash: {f.name} == {val_hashes[h]} ({h[:12]})")

print(f"\nUnique document hashes in validation_notices: {len(val_hashes)}")

# Check what other unique real documents exist in data/documents
all_docs = {}
for f in docs_dir.iterdir():
    if f.is_file():
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        if h not in val_hashes:
            all_docs[h] = f

print(f"Unique additional documents in data/documents: {len(all_docs)}")
