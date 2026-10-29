import os
from pathlib import Path
import pymupdf

val_dir = Path("data/validation_notices")
docs_dir = Path("data/documents")

# List all 22 in validation_notices
val_files = sorted(list(val_dir.glob("notice_*.pdf")))
print(f"Found {len(val_files)} notices in data/validation_notices")

for vf in val_files:
    print(f"  {vf.name} ({vf.stat().st_size} bytes)")
