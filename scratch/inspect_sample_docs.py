import pymupdf
from pathlib import Path
import re

docs_dir = Path("data/documents")
pdf_files = [f for f in docs_dir.iterdir() if f.suffix.lower() == ".pdf"]

print(f"Total PDFs in data/documents: {len(pdf_files)}")

samples = []
for p in pdf_files[:35]:
    try:
        doc = pymupdf.open(p)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        # Find first non-empty lines
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        title_snippet = " // ".join(lines[:3]) if lines else "NO_TEXT"
        samples.append({
            "filename": p.name,
            "hash": p.stem,
            "size": p.stat().st_size,
            "chars": len(text),
            "snippet": title_snippet[:100]
        })
    except Exception as e:
        samples.append({
            "filename": p.name,
            "hash": p.stem,
            "size": p.stat().st_size,
            "chars": 0,
            "snippet": f"ERROR: {e}"
        })

for i, s in enumerate(samples):
    print(f"{i+1:2d}. {s['hash'][:12]} ({s['size']:7d} bytes, {s['chars']:5d} chars) -> {s['snippet']}")
