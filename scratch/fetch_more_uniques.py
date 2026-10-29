from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher
import hashlib

fetcher = SafeFetcher()
val_dir = Path("data/validation_notices")

candidates = [
    ("notice_30_ssc_chsl_final_result.pdf", "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/writeup_final_chsl_2025_07102026.pdf"),
    ("notice_31_ssc_steno_marks_writeup.pdf", "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/Final_Marks_Writeup_07102026.pdf"),
    ("notice_32_nta_sainik_school_corrigendum.pdf", "https://nta.ac.in/Download/Notice/Notice_20241230150912.pdf"),
    ("notice_33_nta_neet_ug_corrigendum.pdf", "https://nta.ac.in/Download/Notice/Notice_20230331120410.pdf"),
]

for filename, url in candidates:
    target = val_dir / filename
    try:
        content, ctype, final_url, _ = fetcher.fetch(url)
        with open(target, "wb") as f:
            f.write(content)
        h = hashlib.sha256(content).hexdigest()
        print(f"Fetched & saved: {filename} ({len(content)} bytes, hash: {h[:12]})")
    except Exception as e:
        print(f"Failed {filename}: {e}")
