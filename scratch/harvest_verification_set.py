import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import fitz

sys.stdout.reconfigure(encoding='utf-8')
from testkart_intelligence.discovery.fetcher import SafeFetcher

# 1. Load all 119 existing restricted hashes
frozen_hashes = set()
for manifest_name in [
    "DEVELOPMENT_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json"
]:
    with open(manifest_name, "r", encoding="utf-8") as f:
        m = json.load(f)
        for doc_name, meta in m["documents"].items():
            h = meta.get("sha256")
            if h:
                frozen_hashes.add(h.lower())

print(f"Total restricted hashes across all 4 benchmark manifests: {len(frozen_hashes)}")

out_dir = Path("data/verification_notices")
out_dir.mkdir(parents=True, exist_ok=True)

fetcher = SafeFetcher()

candidates = [
    # TNPSC Recruitment Notices with multi-stage exam dates and vacancy tables
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/17_2023_ENGLISH.pdf", "title": "Junior Analyst in the Drugs Testing Laboratory"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/33_2022_AP_PSY_ENG.pdf", "title": "Assistant Professor of Psychology cum Clinical Psychologist"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/2018_23_notyfn_APP.pdf", "title": "Assistant Public Prosecutor Grade-II"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/2017_20_NOT_EN_Statistician.pdf", "title": "Statistician in Medical Education Department"},
    
    # NTA Recruitment & Examination Schedules
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20240315131308.pdf", "title": "CSCS Junior Secretariat Assistant Grade LDCE Examination"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20250310132132.pdf", "title": "Examination Schedule for JEE Main 2025 Session-2"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20240629113919.pdf", "title": "Challenge of Provisional Answer Key NEET UG 2024"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20230607230401.pdf", "title": "Release of Admit Card for CUET PG 2023 Examination"},
    
    # UPSC Notices
    {"auth": "Union Public Service Commission", "url": "https://www.upsc.gov.in/whats-new/Combined Geo-Scientist (Preliminary) Examination, 2027/Examination Time Table", "title": "Combined Geo-Scientist Preliminary Examination Time Table"},
    {"auth": "Union Public Service Commission", "url": "https://www.upsc.gov.in/whats-new/Indian Economic Service - Indian Statistical Service Examination, 2026/Interview Schedule", "title": "Indian Economic Service Interview Schedule"}
]

print(f"Candidate count: {len(candidates)}")

harvested = []
seen_hashes = set(frozen_hashes)

for i, cand in enumerate(candidates):
    idx = i + 1
    url = cand["url"]
    auth = cand["auth"]
    title = cand["title"]
    print(f"[{idx}/{len(candidates)}] Fetching {title[:45]}...")
    try:
        content, ctype, final_url, status = fetcher.fetch(url)
        h = hashlib.sha256(content).hexdigest().lower()
        if h in seen_hashes:
            print(f"  COLLISION DETECTED with benchmark hash {h[:12]}. SKIPPING!")
            continue
        
        seen_hashes.add(h)
        ext = "pdf" if (url.lower().endswith(".pdf") or "pdf" in ctype.lower() or content[:4] == b"%PDF") else "html"
        prefix = "tnpsc" if "Tamil Nadu" in auth else ("nta" if "National" in auth else "upsc")
        safe_slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:30].strip("_")
        fname = f"ver_{idx:02d}_{prefix}_{safe_slug}.{ext}"
        target_path = out_dir / fname
        
        with open(target_path, "wb") as f:
            f.write(content)
            
        page_count = 1
        readable = False
        if ext == "pdf":
            try:
                doc = fitz.open(stream=content, filetype="pdf")
                page_count = len(doc)
                sample_text = "".join([doc[p].get_text() for p in range(min(3, page_count))])
                readable = len(sample_text.strip()) > 50
            except Exception as e:
                print(f"  PDF error: {e}")
        else:
            sample_text = content.decode("utf-8", errors="ignore")
            readable = len(sample_text.strip()) > 50
            
        print(f"  Saved {fname} ({len(content):,} bytes, {page_count} pages, readable={readable}) - Hash: {h[:12]}...")
        harvested.append({
            "index": idx,
            "filename": fname,
            "authority": auth,
            "title": title,
            "source_url": url,
            "sha256": h,
            "size_bytes": len(content),
            "page_count": page_count,
            "format": "TEXT_PDF" if ext == "pdf" else "HTML",
            "readable": readable
        })
    except Exception as e:
        print(f"  Error fetching {url}: {e}")

print(f"\nSuccessfully harvested {len(harvested)} verification notices with 0 benchmark collisions.")
with open("scratch/harvested_verification_candidates.json", "w", encoding="utf-8") as f:
    json.dump(harvested, f, indent=2)
