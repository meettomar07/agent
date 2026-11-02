import hashlib
import json
from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher
from bs4 import BeautifulSoup
import pymupdf

# 1. Load all 160 restricted hashes
manifest_files = [
    'DEVELOPMENT_SET_MANIFEST.json',
    'FROZEN_HELD_OUT_DATASET_MANIFEST.json',
    'GENERALIZATION_SET_MANIFEST.json',
    'NEW_VALIDATION_DATASET_MANIFEST.json',
    'PILOT_DATASET_MANIFEST.json',
    'VERIFICATION_SET_MANIFEST.json',
    'PILOT_BATCH_2_MANIFEST.json'
]

restricted_hashes = set()
for mf in manifest_files:
    p = Path(mf)
    if p.exists():
        d = json.loads(p.read_text(encoding='utf-8'))
        for doc in d.get('documents', {}).values():
            if 'sha256' in doc and doc['sha256']:
                restricted_hashes.add(doc['sha256'].lower().strip())

print(f"Loaded {len(restricted_hashes)} restricted hashes.")
fetcher = SafeFetcher()

# Check SSC pages 3..8
ssc_pool = []
for page in range(3, 8):
    if len(ssc_pool) >= 5:
        break
    url = f"https://ssc.gov.in/api/general-website/portal/notice-boards?page={page}&limit=10&contentType=notice-boards&key=createdAt&order=DESC&isAttachment=true&language=english&attributes=id,headline,examId,contentType,redirectUrl,startDate,endDate,language,createdAt"
    try:
        content, _, _, _ = fetcher.fetch(url)
        data = json.loads(content)
        for it in data.get("data", []):
            headline = it.get("headline", "")
            atts = it.get("attachments", [])
            if not atts:
                continue
            path = atts[0].get("path", "").replace("\\", "/")
            if not path:
                continue
            doc_url = f"https://ssc.gov.in/api/attachment/{path}"
            try:
                doc_bytes, _, _, _ = fetcher.fetch(doc_url)
                if len(doc_bytes) < 200:
                    continue
                h = hashlib.sha256(doc_bytes).hexdigest().lower()
                if h not in restricted_hashes:
                    ssc_pool.append({
                        "authority": "Staff Selection Commission",
                        "source_id": "src_ssc",
                        "title": headline,
                        "url": doc_url,
                        "hash": h,
                        "bytes": len(doc_bytes),
                    })
                    print(f"SSC Found: {headline[:60]} (hash: {h[:12]})")
                    if len(ssc_pool) >= 5:
                        break
            except Exception:
                continue
    except Exception as e:
        print("SSC err:", e)

print(f"Total SSC fresh: {len(ssc_pool)}")
