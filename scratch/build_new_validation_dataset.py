import hashlib
import json
from pathlib import Path
import sqlite3
import time
from testkart_intelligence.discovery.fetcher import SafeFetcher

# Load existing restricted hashes
with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
    frozen_manifest = json.load(f)
frozen_hashes = {d["sha256"] for d in frozen_manifest["documents"].values()}

with open("DEVELOPMENT_SET_MANIFEST.json", "r", encoding="utf-8") as f:
    dev_manifest = json.load(f)
dev_hashes = {d["sha256"] for d in dev_manifest["documents"].values()}

restricted_hashes = frozen_hashes.union(dev_hashes)
print(f"Total restricted hashes: {len(restricted_hashes)}")

out_dir = Path("data/new_validation_notices")
out_dir.mkdir(parents=True, exist_ok=True)

fetcher = SafeFetcher()
db = sqlite3.connect("data/testkart.db")
db.row_factory = sqlite3.Row

# Query candidates from each authority
auth_targets = [
    ("Tamil Nadu Public Service Commission", 16, "tnpsc"),
    ("National Testing Agency", 16, "nta"),
    ("Union Public Service Commission", 10, "upsc"),
    ("Staff Selection Commission", 6, "ssc"),
    ("Uttar Pradesh Public Service Commission", 4, "uppsc"),
]

harvested = []
seen_hashes = set(restricted_hashes)

for auth_name, target_count, prefix in auth_targets:
    rows = db.execute(
        "SELECT id, title, normalized_url, category FROM canonical_notices WHERE authority_name = ?",
        (auth_name,)
    ).fetchall()
    
    count_for_auth = 0
    print(f"\nHarvesting for {auth_name} (Target: {target_count})...")
    
    for r in rows:
        if count_for_auth >= target_count:
            break
        url = r["normalized_url"]
        title = r["title"]
        try:
            content, ctype, final_url, status = fetcher.fetch(url)
            h = hashlib.sha256(content).hexdigest()
            if h in seen_hashes:
                # Skip collision
                continue
            
            seen_hashes.add(h)
            count_for_auth += 1
            idx = len(harvested) + 1
            ext = "pdf" if (url.lower().endswith(".pdf") or "pdf" in ctype.lower() or content[:4] == b"%PDF") else "html"
            safe_slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:30].strip("_")
            fname = f"new_val_{idx:02d}_{prefix}_{safe_slug}.{ext}"
            
            target_path = out_dir / fname
            with open(target_path, "wb") as f:
                f.write(content)
                
            harvested.append({
                "index": idx,
                "file_name": fname,
                "authority": auth_name,
                "title": title,
                "url": url,
                "sha256": h,
                "size_bytes": len(content),
                "format": "PDF" if ext == "pdf" else "HTML",
            })
            print(f"  [{count_for_auth}/{target_count}] Saved {fname} ({len(content)} bytes) - {title[:40]}")
        except Exception as e:
            print(f"  Skip {url[:50]}: {e}")
            continue

print(f"\nTotal harvested new notices: {len(harvested)}")
with open("scratch/harvested_raw.json", "w", encoding="utf-8") as f:
    json.dump(harvested, f, indent=2)
