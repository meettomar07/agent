from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher
import hashlib
import json

with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
    manifest = json.load(f)

frozen_hashes = {doc["sha256"] for doc in manifest["documents"].values()}

dev_dir = Path("data/development_notices")
fetcher = SafeFetcher()

more_candidates = [
    ("dev_13_tnpsc_special_competitive_exam.pdf", "https://www.tnpsc.gov.in/Document/english/SCE%20English%20Final_.pdf"),
    ("dev_14_tnpsc_rimc_re_notification.pdf", "https://www.tnpsc.gov.in/Document/english/10_2024_RIMC_Re%20Notification_English_.pdf"),
    ("dev_15_upsc_geo_scientist_table_pdf.pdf", "https://www.upsc.gov.in/sites/default/files/ExamTimeTable-Geol-2027-engl-230926.pdf"),
    ("dev_16_upsc_cdse_namelist_pdf.pdf", "https://www.upsc.gov.in/sites/default/files/WrittenResult-CDSE-II-2026-NameList-Engl-211026.pdf"),
]

for fname, url in more_candidates:
    target = dev_dir / fname
    if not target.exists():
        try:
            content, ctype, final_url, _ = fetcher.fetch(url)
            h = hashlib.sha256(content).hexdigest()
            if h in frozen_hashes:
                print(f"COLLISION: {fname} matches frozen hash. Skipped.")
                continue
            with open(target, "wb") as f:
                f.write(content)
            print(f"Fetched {fname} ({len(content)} bytes)")
        except Exception as e:
            print(f"Failed {fname}: {e}")

all_dev = sorted(list(dev_dir.glob("dev_*")))
print(f"\nTotal verified development set files: {len(all_dev)}")
for f in all_dev:
    print(f"  {f.name} ({f.stat().st_size} bytes)")
