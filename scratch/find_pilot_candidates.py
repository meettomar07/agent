import json
import sqlite3
from pathlib import Path

# Load all hashes, urls, titles from 6 manifests
manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json",
]

all_hashes = set()
all_urls = set()
all_titles = set()

for mf in manifest_files:
    p = Path(mf)
    if not p.exists():
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    docs = data.get("documents", {})
    for k, doc in docs.items():
        if "sha256" in doc and doc["sha256"]:
            all_hashes.add(doc["sha256"].lower().strip())
        if "source_url" in doc and doc["source_url"]:
            all_urls.add(doc["source_url"].lower().strip())
        if "title" in doc and doc["title"]:
            all_titles.add(doc["title"].lower().strip())

print(f"Loaded {len(all_hashes)} existing hashes, {len(all_urls)} urls, {len(all_titles)} titles.")

# Check canonical_notices and notice_versions in testkart.db
conn = sqlite3.connect("data/testkart.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT cn.id, cn.source_id, cn.authority_name, cn.title, cn.normalized_url, cn.notice_number,
           nv.id as version_id, nv.document_hash, nv.storage_path, nv.document_type, nv.raw_text
    FROM canonical_notices cn
    JOIN notice_versions nv ON nv.notice_id = cn.id
    WHERE cn.source_id IN ('src_upsc', 'src_ssc', 'src_nta', 'src_uppsc', 'src_tnpsc')
""").fetchall()

print(f"Total canonical notice versions in DB for 5 authorities: {len(rows)}")

unseen_candidates = []
seen_count = 0

for r in rows:
    h = (r["document_hash"] or "").lower().strip()
    u = (r["normalized_url"] or "").lower().strip()
    t = (r["title"] or "").lower().strip()
    
    if h in all_hashes or u in all_urls or t in all_titles:
        seen_count += 1
        continue
    
    # Check if local storage_path exists
    sp = r["storage_path"]
    exists = False
    if sp and Path(sp).exists():
        exists = True
    elif h:
        # Check in data/documents
        doc_path = Path("data/documents") / f"{h}.pdf"
        if doc_path.exists():
            exists = True
            sp = str(doc_path)
            
    unseen_candidates.append({
        "id": r["id"],
        "source_id": r["source_id"],
        "authority": r["authority_name"],
        "title": r["title"],
        "url": r["normalized_url"],
        "hash": h,
        "storage_path": sp,
        "file_exists": exists,
        "raw_text_len": len(r["raw_text"] or "")
    })

print(f"Seen / overlapping count: {seen_count}")
print(f"Unseen candidate count: {len(unseen_candidates)}")

by_auth = {}
for c in unseen_candidates:
    by_auth.setdefault(c["source_id"], []).append(c)

for auth, cands in by_auth.items():
    print(f"Authority {auth}: {len(cands)} candidates (with files: {sum(1 for x in cands if x['file_exists'])})")
