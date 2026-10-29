import os
import re
from pathlib import Path

email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

root_dir = Path("D:/Agent")
skip_dirs = {".venv", ".git", "__pycache__", ".pytest_cache"}

found_emails = {}

for root, dirs, files in os.walk(root_dir):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for f in files:
        fpath = Path(root) / f
        try:
            # Skip large binary files or database files
            if f.endswith((".db", ".sqlite", ".pyc", ".pdf", ".png", ".jpg", ".exe", ".bin")):
                continue
            text = fpath.read_text(encoding="utf-8", errors="ignore")
            matches = set(email_pattern.findall(text))
            if matches:
                rel_path = str(fpath.relative_to(root_dir)).replace("\\", "/")
                found_emails[rel_path] = list(matches)
        except Exception as e:
            pass

print(f"Scanned files. Found emails in {len(found_emails)} files:")
for path, emails in sorted(found_emails.items()):
    print(f"\n{path}:")
    for em in sorted(emails):
        print(f"  - {em}")
