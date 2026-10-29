import json
import sqlite3
from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher

# Load existing 145 hashes, URLs, titles
manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json",
]
restricted_hashes = set()
restricted_urls = set()
restricted_titles = set()

for mf in manifest_files:
    data = json.loads(Path(mf).read_text(encoding="utf-8"))
    for k, doc in data.get("documents", {}).items():
        if "sha256" in doc and doc["sha256"]:
            restricted_hashes.add(doc["sha256"].lower().strip())
        if "source_url" in doc and doc["source_url"]:
            restricted_urls.add(doc["source_url"].lower().strip())
        if "title" in doc and doc["title"]:
            restricted_titles.add(doc["title"].lower().strip())

print(f"Restricted: {len(restricted_hashes)} hashes, {len(restricted_urls)} URLs, {len(restricted_titles)} titles")

# Check SSC items from API
fetcher = SafeFetcher()
ssc_candidates = []
for page in [1, 2, 3]:
    url = f"https://ssc.gov.in/api/general-website/portal/notice-boards?page={page}&limit=10&contentType=notice-boards&key=createdAt&order=DESC&isAttachment=true&language=english&attributes=id,headline,examId,contentType,redirectUrl,startDate,endDate,language,createdAt"
    try:
        content, _, _, _ = fetcher.fetch(url)
        data = json.loads(content)
        for it in data.get("data", []):
            headline = it.get("headline", "")
            atts = it.get("attachments", [])
            if not atts:
                continue
            att_path = atts[0].get("path", "").replace("\\", "/")
            doc_url = f"https://ssc.gov.in/api/attachment/{att_path}"
            if doc_url.lower() in restricted_urls or headline.lower() in restricted_titles:
                continue
            ssc_candidates.append({
                "headline": headline,
                "url": doc_url,
                "date": it.get("createdAt")
            })
    except Exception as e:
        print("SSC fetch error:", e)

print(f"Found {len(ssc_candidates)} fresh SSC candidates:")
for c in ssc_candidates[:5]:
    print("  ", c["headline"][:70], "|", c["url"][:60])
