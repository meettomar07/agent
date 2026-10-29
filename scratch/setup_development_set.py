"""Fetch and setup a completely separate development set of real notices for extraction debugging and rule development."""

import hashlib
import json
from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher

with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
    manifest = json.load(f)

frozen_hashes = {doc["sha256"] for doc in manifest["documents"].values()}

dev_dir = Path("data/development_notices")
dev_dir.mkdir(parents=True, exist_ok=True)

fetcher = SafeFetcher()

candidates = [
    ("dev_01_ssc_mts_havaldar_result.pdf", "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/writeup_07102026.pdf"),
    ("dev_02_ssc_je_tentative_vacancy_table.pdf", "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/JE_Tentative_Vacancy_08102026.pdf"),
    ("dev_03_nta_exam_calendar_march_2027.pdf", "https://nta.ac.in/Download/Notice/Notice_20260916195948.pdf"),
    ("dev_04_nta_ugc_net_reexam_admit_card.pdf", "https://nta.ac.in/Download/Notice/Notice_20260904214736.pdf"),
    ("dev_05_nta_nittt_exam_schedule.pdf", "https://nta.ac.in/Download/Notice/Notice_20260723191910.pdf"),
    ("dev_06_nta_aiapget_admit_card.pdf", "https://nta.ac.in/Download/Notice/Notice_20260818202733.pdf"),
    ("dev_07_nta_joint_csir_admit_card.pdf", "https://nta.ac.in/Download/Notice/Notice_20260713164141.pdf"),
    ("dev_08_tnpsc_ctse_diploma_recruitment.pdf", "https://www.tnpsc.gov.in/Document/english/CTSE_DIP_Eng_13.08.2024_.pdf"),
    ("dev_09_tnpsc_cts_non_interview_posts.pdf", "https://www.tnpsc.gov.in/Document/english/09_2024_CTS_NONOT_ENGLISH_.pdf"),
    ("dev_10_upsc_homoeopathic_physician_notice.html", "https://www.upsc.gov.in/whats-new/04%20Posts%20of%20Homoeopathic%20Physician%20in%20NDMC/Notice"),
    ("dev_11_upsc_vice_principal_gnctd_notice.html", "https://www.upsc.gov.in/whats-new/704%20Posts%20of%20Vice-Principal%20in%20Education%20department%2C%20GNCTD/Notice"),
    ("dev_12_upsc_manager_sec_officer_result.html", "https://www.upsc.gov.in/whats-new/19%20Posts%20of%20Manager%20Grade%20-%20I%20-%20Section%20Officer%2C%20Ministry%20of%20Defence/Written%20Result"),
]

dev_manifest = {}

for fname, url in candidates:
    target = dev_dir / fname
    if not target.exists():
        try:
            content, ctype, final_url, _ = fetcher.fetch(url)
            with open(target, "wb") as f:
                f.write(content)
            print(f"Fetched {fname} ({len(content)} bytes)")
        except Exception as e:
            print(f"Failed to fetch {fname} ({url}): {e}")
            continue
    else:
        content = target.read_bytes()

    h = hashlib.sha256(content).hexdigest()
    if h in frozen_hashes:
        print(f"ERROR: Collision with frozen held-out hash! Removing {fname}")
        target.unlink()
        continue

    dev_manifest[fname] = {
        "sha256": h,
        "size_bytes": len(content),
        "source_url": url,
    }

print(f"\nCreated separate development set with {len(dev_manifest)} verified non-held-out notices.")
with open("DEVELOPMENT_SET_MANIFEST.json", "w", encoding="utf-8") as f:
    json.dump(dev_manifest, f, indent=2)
