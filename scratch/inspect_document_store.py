import sqlite3
import os
from pathlib import Path
import pymupdf

docs_dir = Path("data/documents")
files = list(docs_dir.iterdir())
print(f"Total files in data/documents: {len(files)}")

pdf_files = [f for f in files if f.suffix.lower() == ".pdf"]
html_files = [f for f in files if f.suffix.lower() == ".html"]
print(f"PDF files: {len(pdf_files)}, HTML files: {len(html_files)}")

# Check text extractability for sample PDFs
text_pdfs = 0
scanned_pdfs = 0
for p in pdf_files:
    try:
        doc = pymupdf.open(p)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        if len(text.strip()) > 50:
            text_pdfs += 1
        else:
            scanned_pdfs += 1
    except Exception:
        scanned_pdfs += 1

print(f"Readable Text PDFs: {text_pdfs}, Scanned/Low-text PDFs: {scanned_pdfs}")
