import os
from pathlib import Path
import pymupdf
import sqlite3

docs_dir = Path("data/documents")
conn = sqlite3.connect("data/testkart.db")
c = conn.cursor()

# Find real documents (size > 10 KB or in notice_versions or in FACT_EXTRACTION_EVALUATION.csv)
large_docs = []
for p in docs_dir.iterdir():
    if p.is_file() and p.stat().st_size > 10000:
        large_docs.append(p)

print(f"Total documents > 10 KB in data/documents: {len(large_docs)}")

doc_details = []
for p in large_docs:
    sz = p.stat().st_size
    stem = p.stem
    ext = p.suffix.lower()
    
    # Check if in notice_versions or canonical_notices
    row = c.execute("SELECT cn.id, cn.authority_name, cn.title, cn.classification, cn.recency_status FROM notice_versions nv JOIN canonical_notices cn ON nv.notice_id = cn.id WHERE nv.document_hash = ?", (stem,)).fetchone()
    
    char_count = 0
    first_lines = ""
    if ext == ".pdf":
        try:
            doc = pymupdf.open(p)
            text = ""
            for page in doc:
                text += page.get_text()
            char_count = len(text)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            first_lines = " | ".join(lines[:2])
            doc.close()
        except Exception as e:
            first_lines = f"PDF_ERROR: {e}"
    elif ext == ".html":
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            char_count = len(text)
            first_lines = text[:150].replace("\n", " ")
        except Exception as e:
            first_lines = f"HTML_ERROR: {e}"
            
    doc_details.append({
        "path": p,
        "stem": stem,
        "ext": ext,
        "size": sz,
        "chars": char_count,
        "db_info": row,
        "snippet": first_lines[:80]
    })

print(f"\nIndexed/Analyzed documents: {len(doc_details)}")
for i, d in enumerate(doc_details):
    auth = d["db_info"][1] if d["db_info"] else "UNKNOWN_IN_DB"
    title = d["db_info"][2] if d["db_info"] else d["snippet"]
    print(f"{i+1:2d}. [{d['ext'].upper()}] {d['stem'][:10]}... | {d['size']:7d} bytes | {d['chars']:6d} chars | {auth[:20]} | {title[:50]}")
