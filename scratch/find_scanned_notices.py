import pymupdf
from pathlib import Path

notices_dir = Path("data/validation_notices")
pdf_files = sorted(list(notices_dir.glob("*.pdf")))

print(f"Total PDFs in validation_notices: {len(pdf_files)}")
scanned = []
for p in pdf_files:
    doc = pymupdf.open(p)
    total_chars = 0
    for page in doc:
        total_chars += len(page.get_text("text").strip())
    doc.close()
    if total_chars < 50:
        scanned.append((p.name, total_chars))

print(f"\nScanned PDFs (< 50 text chars): {len(scanned)}")
for name, chars in scanned:
    print(f"  {name}: {chars} chars")
