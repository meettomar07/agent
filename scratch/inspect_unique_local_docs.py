import hashlib
import json
from pathlib import Path
import pymupdf

with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r") as f:
    frozen_manifest = json.load(f)
frozen_hashes = {d["sha256"] for d in frozen_manifest["documents"].values()}

with open("DEVELOPMENT_SET_MANIFEST.json", "r") as f:
    dev_manifest = json.load(f)
dev_hashes = {d["sha256"] for d in dev_manifest["documents"].values()}

restricted_hashes = frozen_hashes.union(dev_hashes)

doc_dir = Path("data/documents")
all_files = list(doc_dir.glob("*"))

unique_available = []
for p in all_files:
    if p.stem not in restricted_hashes:
        unique_available.append(p)

real_docs = []
for p in unique_available:
    sz = p.stat().st_size
    text_chars = 0
    snippet = ""
    is_pdf = p.suffix.lower() == ".pdf"
    if is_pdf:
        try:
            doc = pymupdf.open(p)
            for page in doc:
                text_chars += len(page.get_text())
            if len(doc) > 0:
                snippet = doc[0].get_text()[:120].replace("\n", " ")
            doc.close()
        except Exception:
            pass
    else:
        text = p.read_text(encoding="utf-8", errors="replace")
        text_chars = len(text)
        snippet = text[:120].replace("\n", " ")

    # sanitize snippet
    clean_snippet = snippet.encode("ascii", "replace").decode("ascii")
    real_docs.append({
        "path": p,
        "name": p.name,
        "size": sz,
        "chars": text_chars,
        "snippet": clean_snippet,
    })

real_docs.sort(key=lambda x: -x["size"])
print(f"Top 30 unique available files (non-restricted):")
for i, d in enumerate(real_docs[:30]):
    print(f"{i+1:2d}. {d['name'][:24]}... | {d['size']:7d} bytes | {d['chars']:6d} chars | {d['snippet'][:50]}")
