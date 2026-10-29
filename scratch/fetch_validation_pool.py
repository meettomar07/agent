from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher

fetcher = SafeFetcher()
val_dir = Path("data/validation_notices")

candidates = [
    ("notice_23_nta_cuet_ug_cancellation.pdf", "https://nta.ac.in/Download/Notice/Notice_20250514161031.pdf"),
    ("notice_30_ssc_constable_gd_writeup.pdf", "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/writeup_23102026.pdf"),
    ("notice_31_ssc_phase_xiv_writeup.pdf", "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/writeup_rhq.pdf"),
    ("notice_32_tnpsc_group_v_a_notification.pdf", "https://www.tnpsc.gov.in/Document/english/Group%20V%20A%20%20ENGLISH_.pdf"),
    ("notice_33_nta_nift_application_notice.pdf", "https://nta.ac.in/Download/Notice/Notice_20261016183525.pdf"),
]

for filename, url in candidates:
    target = val_dir / filename
    if target.exists():
        print(f"Already exists: {filename} ({target.stat().st_size} bytes)")
        continue
    try:
        content, ctype, final_url, _ = fetcher.fetch(url)
        with open(target, "wb") as f:
            f.write(content)
        print(f"Fetched & saved: {filename} ({len(content)} bytes, {ctype})")
    except Exception as e:
        print(f"Failed to fetch {filename} ({url}): {e}")

all_val = sorted(list(val_dir.glob("notice_*")))
print(f"\nTotal official notices in data/validation_notices: {len(all_val)}")
for i, f in enumerate(all_val):
    print(f"  {i+1:2d}. {f.name} ({f.stat().st_size} bytes)")
