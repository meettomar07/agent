import os
import re
from pathlib import Path

root_dir = Path("D:/Agent")
skip_dirs = {".venv", ".git", "__pycache__", ".pytest_cache"}

keywords = [
    "testkart.in",
    "testkart.com",
    "OWNER_EMAIL",
    "ADMIN_EMAIL",
    "NOTIFICATION_EMAIL",
    "SMTP_",
    "MAIL_",
]

results = {kw: [] for kw in keywords}

for root, dirs, files in os.walk(root_dir):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for f in files:
        fpath = Path(root) / f
        if f.endswith((".db", ".sqlite", ".pyc", ".pdf", ".png", ".jpg", ".exe", ".bin")):
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
            for kw in keywords:
                if kw in text or kw.lower() in text.lower():
                    rel = str(fpath.relative_to(root_dir)).replace("\\", "/")
                    results[kw].append(rel)
        except Exception:
            pass

for kw, files in results.items():
    print(f"\nKeyword: {kw} (found in {len(files)} files)")
    for f in sorted(set(files))[:20]:
        print(f"  - {f}")
