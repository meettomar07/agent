import hashlib
import json
from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher
from bs4 import BeautifulSoup

# Load all 145 restricted hashes
manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json",
]
restricted_hashes = set()
for mf in manifest_files:
    data = json.loads(Path(mf).read_text(encoding="utf-8"))
    for k, doc in data.get("documents", {}).items():
        if "sha256" in doc and doc["sha256"]:
            restricted_hashes.add(doc["sha256"].lower().strip())

print(f"Loaded {len(restricted_hashes)} restricted hashes.")
fetcher = SafeFetcher()

# 1. SSC: scan pages 1..5
ssc_found = []
for page in range(1, 6):
    if len(ssc_found) >= 3:
        break
    url = f"https://ssc.gov.in/api/general-website/portal/notice-boards?page={page}&limit=10&contentType=notice-boards&key=createdAt&order=DESC&isAttachment=true&language=english&attributes=id,headline,examId,contentType,redirectUrl,startDate,endDate,language,createdAt"
    try:
        content, _, _, _ = fetcher.fetch(url)
        data = json.loads(content)
        for it in data.get("data", []):
            headline = it.get("headline", "")
            atts = it.get("attachments", [])
            if not atts:
                continue
            path = atts[0].get("path", "").replace("\\", "/")
            if not path:
                continue
            doc_url = f"https://ssc.gov.in/api/attachment/{path}"
            # Fetch doc
            try:
                doc_bytes, _, _, _ = fetcher.fetch(doc_url)
                h = hashlib.sha256(doc_bytes).hexdigest().lower()
                if h not in restricted_hashes:
                    ssc_found.append({
                        "source_id": "src_ssc",
                        "authority": "Staff Selection Commission",
                        "title": headline,
                        "url": doc_url,
                        "bytes": doc_bytes,
                        "hash": h,
                        "ext": "pdf"
                    })
                    print(f"SSC Found: {headline[:60]} (hash: {h[:12]})")
                    if len(ssc_found) >= 3:
                        break
            except Exception:
                continue
    except Exception as e:
        print("SSC error:", e)

# 2. UPSC: scan whats-new
upsc_found = []
try:
    content, _, _, _ = fetcher.fetch("https://www.upsc.gov.in/whats-new")
    soup = BeautifulSoup(content, "html.parser")
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = " ".join(a.text.split())
        if not text or len(text) < 10 or "view" in text.lower():
            continue
        if href.startswith("/"):
            full_url = f"https://www.upsc.gov.in{href}"
        elif href.startswith("http"):
            full_url = href
        else:
            continue
        try:
            doc_bytes, _, _, _ = fetcher.fetch(full_url)
            if len(doc_bytes) < 300:
                continue
            h = hashlib.sha256(doc_bytes).hexdigest().lower()
            if h not in restricted_hashes:
                ext = "pdf" if full_url.endswith(".pdf") else "html"
                upsc_found.append({
                    "source_id": "src_upsc",
                    "authority": "Union Public Service Commission",
                    "title": text,
                    "url": full_url,
                    "bytes": doc_bytes,
                    "hash": h,
                    "ext": ext
                })
                print(f"UPSC Found: {text[:60]} (hash: {h[:12]})")
                if len(upsc_found) >= 3:
                    break
        except Exception:
            continue
except Exception as e:
    print("UPSC error:", e)

# 3. NTA: Notice board archive
nta_found = []
try:
    content, _, _, _ = fetcher.fetch("https://nta.ac.in/NoticeBoardArchive")
    soup = BeautifulSoup(content, "html.parser")
    rows = soup.find_all("tr")
    for tr in rows:
        a = tr.find("a")
        if not a:
            continue
        title = " ".join(tr.text.split())
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
            doc_bytes, _, _, _ = fetcher.fetch(full_url)
            h = hashlib.sha256(doc_bytes).hexdigest().lower()
            if h not in restricted_hashes:
                nta_found.append({
                    "source_id": "src_nta",
                    "authority": "National Testing Agency",
                    "title": title,
                    "url": full_url,
                    "bytes": doc_bytes,
                    "hash": h,
                    "ext": "pdf"
                })
                print(f"NTA Found: {title[:60]} (hash: {h[:12]})")
                if len(nta_found) >= 3:
                    break
        except Exception:
            continue
except Exception as e:
    print("NTA error:", e)

# 4. UPPSC: Notifications page
uppsc_found = []
try:
    content, _, _, _ = fetcher.fetch("https://uppsc.up.nic.in/CandidatePages/Notifications.aspx")
    soup = BeautifulSoup(content, "html.parser")
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if "view_advertisement" in href.lower() or "advertisement" in href.lower():
            if href.startswith("../"):
                full_url = f"https://uppsc.up.nic.in/{href[3:]}"
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = f"https://uppsc.up.nic.in/OuterPages/{href}"
            try:
                doc_bytes, _, _, _ = fetcher.fetch(full_url)
                h = hashlib.sha256(doc_bytes).hexdigest().lower()
                if h not in restricted_hashes:
                    uppsc_found.append({
                        "source_id": "src_uppsc",
                        "authority": "Uttar Pradesh Public Service Commission",
                        "title": f"UPPSC Advertisement ({href.split('ID=')[-1].split('&')[0]})",
                        "url": full_url,
                        "bytes": doc_bytes,
                        "hash": h,
                        "ext": "html"
                    })
                    print(f"UPPSC Found: (hash: {h[:12]})")
                    if len(uppsc_found) >= 3:
                        break
            except Exception:
                continue
except Exception as e:
    print("UPPSC error:", e)

# 5. TNPSC: Notifications page
tnpsc_found = []
try:
    content, _, _, _ = fetcher.fetch("https://www.tnpsc.gov.in/English/notification.aspx")
    soup = BeautifulSoup(content, "html.parser")
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = " ".join(a.text.split())
        if not href.lower().endswith(".pdf") or not text or len(text) < 5:
            continue
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            full_url = f"https://www.tnpsc.gov.in{href}"
        else:
            full_url = f"https://www.tnpsc.gov.in/English/{href}"
        try:
            doc_bytes, _, _, _ = fetcher.fetch(full_url)
            h = hashlib.sha256(doc_bytes).hexdigest().lower()
            if h not in restricted_hashes:
                tnpsc_found.append({
                    "source_id": "src_tnpsc",
                    "authority": "Tamil Nadu Public Service Commission",
                    "title": text,
                    "url": full_url,
                    "bytes": doc_bytes,
                    "hash": h,
                    "ext": "pdf"
                })
                print(f"TNPSC Found: {text[:60]} (hash: {h[:12]})")
                if len(tnpsc_found) >= 3:
                    break
        except Exception:
            continue
except Exception as e:
    print("TNPSC error:", e)

print(f"\nSummary of fresh 0-collision documents found:")
print(f"  SSC: {len(ssc_found)}")
print(f"  UPSC: {len(upsc_found)}")
print(f"  NTA: {len(nta_found)}")
print(f"  UPPSC: {len(uppsc_found)}")
print(f"  TNPSC: {len(tnpsc_found)}")
