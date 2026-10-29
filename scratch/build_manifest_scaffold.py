"""Build NEW_VALIDATION_DATASET_MANIFEST.json with ground truth for all 52 official notices."""

import hashlib
import json
from pathlib import Path
import re
import pymupdf

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor

pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()

new_val_dir = Path("data/new_validation_notices")
files = sorted(list(new_val_dir.glob("*")))

print(f"Total files in new_validation_notices: {len(files)}")

# Build manifest dictionary
manifest = {
    "dataset_name": "Testkart New Independent Validation Dataset (52 Canonical Notices)",
    "created_at": "2026-10-27T14:45:00Z",
    "status": "INDEPENDENT_EVALUATION_GATE",
    "total_documents": len(files),
    "authorities_distribution": {
        "Tamil Nadu Public Service Commission": 16,
        "National Testing Agency": 16,
        "Union Public Service Commission": 10,
        "Staff Selection Commission": 7,
        "Uttar Pradesh Public Service Commission": 3,
    },
    "documents": {},
}

for p in files:
    fname = p.name
    content = p.read_bytes()
    h = hashlib.sha256(content).hexdigest()
    sz = len(content)
    is_pdf = fname.endswith(".pdf")
    
    if is_pdf:
        full_text, pages, page_count = pdf_ext.extract(content)
        is_scanned = any(pg.get("is_scanned") for pg in pages)
    else:
        text_str = content.decode("utf-8", errors="replace")
        full_text, pages, page_count = html_ext.extract(text_str)
        is_scanned = False
        page_count = 1

    # Extract authority
    if "_tnpsc_" in fname:
        auth = "Tamil Nadu Public Service Commission"
    elif "_nta_" in fname:
        auth = "National Testing Agency"
    elif "_upsc_" in fname:
        auth = "Union Public Service Commission"
    elif "_uppsc_" in fname:
        auth = "Uttar Pradesh Public Service Commission"
    elif "_ssc_" in fname:
        auth = "Staff Selection Commission"
    else:
        auth = "Unknown"

    manifest["documents"][fname] = {
        "sha256": h,
        "size_bytes": sz,
        "authority": auth,
        "format": "SCANNED_PDF" if is_scanned else ("TEXT_PDF" if is_pdf else "HTML"),
        "readable": True,
        "is_scanned": is_scanned,
        "page_count": page_count,
        "chars_extracted": len(full_text),
    }

print(f"Manifest initialized with {len(manifest['documents'])} documents.")
with open("scratch/manifest_scaffold.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
