import hashlib
import json
from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher

# Load existing restricted hashes
with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
    frozen_manifest = json.load(f)
frozen_hashes = {d["sha256"] for d in frozen_manifest["documents"].values()}

with open("DEVELOPMENT_SET_MANIFEST.json", "r", encoding="utf-8") as f:
    dev_manifest = json.load(f)
dev_hashes = {d["sha256"] for d in dev_manifest["documents"].values()}

out_dir = Path("data/new_validation_notices")
existing_new_files = list(out_dir.glob("*"))
existing_new_hashes = set()
for p in existing_new_files:
    existing_new_hashes.add(hashlib.sha256(p.read_bytes()).hexdigest())

all_restricted = frozen_hashes.union(dev_hashes).union(existing_new_hashes)
print(f"Total restricted hashes: {len(all_restricted)}")

fetcher = SafeFetcher()

# Fetch page 2 and page 3 of SSC
ssc_items = []
for page in [2, 3]:
    url = f"https://ssc.gov.in/api/general-website/portal/notice-boards?page={page}&limit=10&contentType=notice-boards&key=createdAt&order=DESC&isAttachment=true&language=english&attributes=id,headline,examId,contentType,redirectUrl,startDate,endDate,language,createdAt"
    content, _, _, _ = fetcher.fetch(url)
    data = json.loads(content)
    ssc_items.extend(data.get("data", []))

print(f"Found {len(ssc_items)} SSC items from pages 2 and 3")

added_ssc = 0
current_count = len(existing_new_files)

for it in ssc_items:
    if added_ssc >= 7:
        break
    atts = it.get("attachments", [])
    if not atts:
        continue
    att = atts[0]
    fname = att.get("fileName")
    path = att.get("path", "").replace("\\", "/")
    if not path:
        continue
    pdf_url = f"https://ssc.gov.in/api/attachment/{path}"
    title = it.get("headline", "").strip()
    
    try:
        pdf_content, ctype, _, status = fetcher.fetch(pdf_url)
        h = hashlib.sha256(pdf_content).hexdigest()
        if h in all_restricted:
            print(f"Skipping hash collision: {title[:40]}")
            continue
        
        all_restricted.add(h)
        current_count += 1
        added_ssc += 1
        safe_slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:30].strip("_")
        target_name = f"new_val_{current_count:02d}_ssc_{safe_slug}.pdf"
        target_path = out_dir / target_name
        target_path.write_bytes(pdf_content)
        print(f"[{added_ssc}/7] Saved {target_name} ({len(pdf_content)} bytes) - {title[:40]}")
    except Exception as e:
        print(f"Failed fetch {pdf_url}: {e}")

print(f"\nTotal notices now in data/new_validation_notices: {len(list(out_dir.glob('*')))}")
