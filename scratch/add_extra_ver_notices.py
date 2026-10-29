from pathlib import Path
import hashlib
import json
import fitz
from testkart_intelligence.discovery.fetcher import SafeFetcher

fetcher = SafeFetcher()
out_dir = Path("data/verification_notices")
out_dir.mkdir(parents=True, exist_ok=True)

new_additions = [
    {"idx": 1, "auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/8_2012_not_eng_eo_grI.pdf", "title": "Executive Officer Grade-I", "slug": "executive_officer_grade_i"},
    {"idx": 11, "auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/1_2012_not_eng_asst_geo_chemist.pdf", "title": "Assistant Geo Chemist", "slug": "assistant_geo_chemist"}
]

for item in new_additions:
    idx = item["idx"]
    content, _, _, _ = fetcher.fetch(item["url"])
    h = hashlib.sha256(content).hexdigest().lower()
    fname = f"ver_{idx:02d}_tnpsc_{item['slug']}.pdf"
    fpath = out_dir / fname
    with open(fpath, "wb") as f:
        f.write(content)
    doc = fitz.open(stream=content, filetype="pdf")
    print(f"Saved {fname} ({len(content)} bytes, {len(doc)} pages) - Hash: {h[:12]}")
