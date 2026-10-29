import hashlib
import json
from pathlib import Path
import pymupdf

with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
    manifest = json.load(f)

frozen_hashes = {doc["sha256"] for doc in manifest["documents"].values()}
docs_dir = Path("data/documents")

dev_candidates = []
for p in docs_dir.iterdir():
    if not p.is_file():
        continue
    content = p.read_bytes()
    h = hashlib.sha256(content).hexdigest()
    if h in frozen_hashes:
        continue
        
    ext = p.suffix.lower()
    sz = len(content)
    if ext == ".pdf":
        try:
            doc = pymupdf.open(p)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            chars = len(text.strip())
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            snippet = " // ".join(lines[:3]) if lines else "EMPTY"
        except Exception as e:
            chars = 0
            snippet = f"ERR: {e}"
    else:
        text = content.decode("utf-8", errors="replace")
        chars = len(text.strip())
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        snippet = " // ".join(lines[:3]) if lines else "EMPTY"
        
    dev_candidates.append({
        "path": p,
        "hash": h,
        "ext": ext,
        "size": sz,
        "chars": chars,
        "snippet": snippet[:100]
    })

print(f"Total non-held-out candidates in data/documents: {len(dev_candidates)}")
# Filter for meaningful documents with chars > 50 or size > 1000
meaningful = [d for d in dev_candidates if d["chars"] > 50 and d["size"] > 1000]
print(f"Meaningful text candidates: {len(meaningful)}")

for i, m in enumerate(meaningful[:25]):
    snip_safe = m["snippet"].encode("ascii", errors="replace").decode("ascii")
    print(f"{i+1:2d}. [{m['ext']}] {m['hash'][:10]} | {m['size']:7d}b | {m['chars']:5d}c | {snip_safe[:60]}")
