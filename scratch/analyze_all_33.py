from pathlib import Path
import hashlib
import pymupdf
import re

val_dir = Path("data/validation_notices")
files = sorted(list(val_dir.glob("notice_*")))

print(f"Analyzing {len(files)} official documents in validation directory:")

summary = []
for f in files:
    ext = f.suffix.lower()
    sz = f.stat().st_size
    content = f.read_bytes()
    h = hashlib.sha256(content).hexdigest()
    
    is_scanned = False
    text = ""
    pages = 1
    if ext == ".pdf":
        try:
            doc = pymupdf.open(f)
            pages = len(doc)
            for page in doc:
                text += page.get_text()
            doc.close()
            if len(text.strip()) < 50:
                is_scanned = True
        except Exception as e:
            text = f"ERR: {e}"
            is_scanned = True
    else:
        text = content.decode("utf-8", errors="replace")
        
    first_few = [l.strip() for l in text.split("\n") if l.strip()][:3]
    summary.append({
        "name": f.name,
        "hash": h,
        "format": "SCANNED_PDF" if is_scanned else ("TEXT_PDF" if ext == ".pdf" else "HTML"),
        "pages": pages,
        "chars": len(text.strip()),
        "snippet": " // ".join(first_few)[:80]
    })

for s in summary:
    snippet_safe = s['snippet'].encode('ascii', errors='replace').decode('ascii')
    print(f"[{s['format']:11s}] {s['name']:45s} | {s['pages']:2d}p | {s['chars']:6d}c | {s['hash'][:10]} | {snippet_safe}")
