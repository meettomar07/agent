import hashlib
import json
from pathlib import Path
import sqlite3
import fitz
import io
from testkart_intelligence.discovery.fetcher import SafeFetcher

# 1. Load all 98 existing restricted hashes
with open("DEVELOPMENT_SET_MANIFEST.json", "r", encoding="utf-8") as f:
    dev_m = json.load(f)
with open("NEW_VALIDATION_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
    val_m = json.load(f)
with open("FROZEN_HELD_OUT_DATASET_MANIFEST.json", "r", encoding="utf-8") as f:
    held_m = json.load(f)

restricted_hashes = {v["sha256"].lower() for v in dev_m["documents"].values()} | \
                    {v["sha256"].lower() for v in val_m["documents"].values()} | \
                    {v["sha256"].lower() for v in held_m["documents"].values()}

print(f"Total restricted hashes across 3 existing sets: {len(restricted_hashes)}")

out_dir = Path("data/generalization_notices")
out_dir.mkdir(parents=True, exist_ok=True)

fetcher = SafeFetcher()
conn = sqlite3.connect("data/testkart.db")
cur = conn.cursor()

# Candidate selections from canonical_notices
candidates = [
    # State: TNPSC - Diverse recruitment notifications
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/09_23_Asst_Jailor_ENG.pdf", "title": "Assistant Jailor (Men & Women)"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/03_2023_TOURIST_OFFICER_ENGLISH.pdf", "title": "Tourist Officer"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/02_2023_RI_ENG.pdf", "title": "Road Inspector in Rural Development"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/10_2023_JSO_ENG.pdf", "title": "Junior Scientific Officer"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/11_2023_GEOLOGY_ENG.pdf", "title": "Combined Geology Subordinate Service Examination"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/12_2023_CJ_ENG.pdf", "title": "Civil Judge in Tamil Nadu State Judicial Service"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/13_2023_Eng.pdf", "title": "Combined Research Assistant in Various Subordinate Services"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/14_2023_English.pdf", "title": "Assistant Training Officer & Junior Technical Assistant"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/05_2024_ENG_.pdf", "title": "Combined Civil Services Group I-B and I-C Services"},
    {"auth": "Tamil Nadu Public Service Commission", "url": "https://www.tnpsc.gov.in/Document/english/04_2023_Combined Library_ English.pdf", "title": "Combined Library Examination"},
    
    # Central: NTA - Recruitment, Entrance, and Non-Recruitment controls
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20260813154925.pdf", "title": "Advertisement for Video Editor cum Graphic Designer"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20260725210713.pdf", "title": "Engagement of General Manager - Assessment, R&D"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20260725210637.pdf", "title": "Engagement of General Manager - Information Security"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20260725210603.pdf", "title": "Engagement of General Manager - Test Centre Network"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20260725210507.pdf", "title": "Engagement of General Manager - Vigilance, Investigation"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20260801151430.pdf", "title": "Engagement of Young Professionals (YPs)"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20260901232135.pdf", "title": "Inviting Online Application Form for RIMC"},
    {"auth": "National Testing Agency", "url": "https://nta.ac.in/Download/Notice/Notice_20260801105217.pdf", "title": "Correction in Application Form AIAPGET 2026"},

    # Central: UPSC - Notices and Results
    {"auth": "Union Public Service Commission", "url": "https://www.upsc.gov.in/whats-new/04 Posts of Homoeopathic Physician in NDMC/Notice", "title": "04 Posts of Homoeopathic Physician in NDMC Notice"},
    {"auth": "Union Public Service Commission", "url": "https://www.upsc.gov.in/whats-new/704 Posts of Vice-Principal in Education department, GNCTD/Notice", "title": "704 Posts of Vice-Principal in Education Department Notice"},
    {"auth": "Union Public Service Commission", "url": "https://www.upsc.gov.in/whats-new/Combined Geo-Scientist (Preliminary) Examination, 2027/Examination Time Table", "title": "Combined Geo-Scientist Preliminary Examination Time Table"},
    {"auth": "Union Public Service Commission", "url": "https://www.upsc.gov.in/whats-new/Indian Economic Service - Indian Statistical Service Examination, 2026/Interview Schedule", "title": "Indian Economic Service Interview Schedule"}
]

print(f"Candidate count: {len(candidates)}")

harvested = []
seen_hashes = set(restricted_hashes)

for i, cand in enumerate(candidates):
    idx = i + 1
    url = cand["url"]
    auth = cand["auth"]
    title = cand["title"]
    print(f"[{idx}/{len(candidates)}] Fetching {title[:40]}...")
    try:
        content, ctype, final_url, status = fetcher.fetch(url)
        h = hashlib.sha256(content).hexdigest().lower()
        if h in seen_hashes:
            print(f"  COLLISION DETECTED with existing benchmarks: {h}. SKIPPING!")
            continue
        
        seen_hashes.add(h)
        ext = "pdf" if (url.lower().endswith(".pdf") or "pdf" in ctype.lower() or content[:4] == b"%PDF") else "html"
        prefix = "tnpsc" if "Tamil Nadu" in auth else ("nta" if "National" in auth else "upsc")
        safe_slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:30].strip("_")
        fname = f"gen_{idx:02d}_{prefix}_{safe_slug}.{ext}"
        target_path = out_dir / fname
        
        with open(target_path, "wb") as f:
            f.write(content)
            
        # Verify readability
        readable = False
        page_count = 1
        sample_text = ""
        if ext == "pdf":
            try:
                doc = fitz.open(stream=content, filetype="pdf")
                page_count = len(doc)
                sample_text = "".join([doc[p].get_text() for p in range(min(3, page_count))])
                readable = len(sample_text.strip()) > 50
            except Exception as e:
                print(f"  PDF read error: {e}")
        else:
            sample_text = content.decode("utf-8", errors="ignore")
            readable = len(sample_text.strip()) > 50
            
        print(f"  Saved {fname} ({len(content)} bytes, {page_count} pages, readable: {readable}) - Hash: {h[:12]}...")
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

print(f"\nSuccessfully harvested {len(harvested)} independent generalization notices.")
with open("scratch/harvested_generalization_candidates.json", "w", encoding="utf-8") as f:
    json.dump(harvested, f, indent=2)
