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

results = {}

# 1. SSC
ssc_items = [
    {
        "authority": "Staff Selection Commission",
        "source_id": "src_ssc",
        "title": "Recruitment of Scientific Assistant in IMD Examination, 2026",
        "url": "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/writeup_scientific_asst_imd.pdf",
    },
    {
        "authority": "Staff Selection Commission",
        "source_id": "src_ssc",
        "title": "Important Notice - Schedule of Examination for Multi Tasking Staff (MTS)",
        "url": "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/schedule_of_exam_mts.pdf",
    },
    {
        "authority": "Staff Selection Commission",
        "source_id": "src_ssc",
        "title": "Important Notice - Instructions for PwBD Candidates with Locomotor Disability",
        "url": "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/instructions_pwbd_candidates.pdf",
    }
]

# 2. NTA: check archive
nta_pool = []
try:
    content, _, _, _ = fetcher.fetch("https://nta.ac.in/NoticeBoardArchive")
    soup = BeautifulSoup(content, "html.parser")
    for tr in soup.find_all("tr"):
        a = tr.find("a")
        if not a:
            continue
        text = " ".join(tr.text.split())
        href = a.get("href", "")
        if not href.endswith(".pdf"):
            continue
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            full_url = f"https://nta.ac.in{href}"
        else:
            full_url = f"https://nta.ac.in/{href}"
        try:
            b, _, _, _ = fetcher.fetch(full_url)
            if len(b) < 300:
                continue
            h = hashlib.sha256(b).hexdigest().lower()
            if h not in restricted_hashes:
                nta_pool.append({
                    "authority": "National Testing Agency",
                    "source_id": "src_nta",
                    "title": text,
                    "url": full_url,
                    "hash": h,
                    "bytes": len(b)
                })
                print(f"NTA Found: {text[:60]} (hash: {h[:12]})")
                if len(nta_pool) >= 4:
                    break
        except Exception:
            continue
except Exception as e:
    print("NTA err:", e)

# 3. UPSC: whats-new
upsc_pool = []
try:
    content, _, _, _ = fetcher.fetch("https://www.upsc.gov.in/whats-new")
    soup = BeautifulSoup(content, "html.parser")
    for a in soup.find_all("a"):
        text = " ".join(a.text.split())
        href = a.get("href", "")
        if len(text) < 15 or "view" in text.lower():
            continue
        if href.startswith("/"):
            full_url = f"https://www.upsc.gov.in{href}"
        elif href.startswith("http"):
            full_url = href
        else:
            continue
        try:
            b, _, _, _ = fetcher.fetch(full_url)
            if len(b) < 300:
                continue
            h = hashlib.sha256(b).hexdigest().lower()
            if h not in restricted_hashes:
                upsc_pool.append({
                    "authority": "Union Public Service Commission",
                    "source_id": "src_upsc",
                    "title": text,
                    "url": full_url,
                    "hash": h,
                    "bytes": len(b)
                })
                print(f"UPSC Found: {text[:60]} (hash: {h[:12]})")
                if len(upsc_pool) >= 4:
                    break
        except Exception:
            continue
except Exception as e:
    print("UPSC err:", e)

# 4. TNPSC: notification.aspx
tnpsc_pool = []
try:
    content, _, _, _ = fetcher.fetch("https://www.tnpsc.gov.in/English/notification.aspx")
    soup = BeautifulSoup(content, "html.parser")
    for a in soup.find_all("a"):
        text = " ".join(a.text.split())
        href = a.get("href", "")
        if not href.lower().endswith(".pdf") or len(text) < 5:
            continue
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            full_url = f"https://www.tnpsc.gov.in{href}"
        else:
            full_url = f"https://www.tnpsc.gov.in/English/{href}"
        try:
            b, _, _, _ = fetcher.fetch(full_url)
            if len(b) < 300:
                continue
            h = hashlib.sha256(b).hexdigest().lower()
            if h not in restricted_hashes:
                tnpsc_pool.append({
                    "authority": "Tamil Nadu Public Service Commission",
                    "source_id": "src_tnpsc",
                    "title": text,
                    "url": full_url,
                    "hash": h,
                    "bytes": len(b)
                })
                print(f"TNPSC Found: {text[:60]} (hash: {h[:12]})")
                if len(tnpsc_pool) >= 4:
                    break
        except Exception:
            continue
except Exception as e:
    print("TNPSC err:", e)

print(f"\nDiscovered counts: NTA={len(nta_pool)}, UPSC={len(upsc_pool)}, TNPSC={len(tnpsc_pool)}")
