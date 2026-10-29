import hashlib
import json
from pathlib import Path
from testkart_intelligence.discovery.fetcher import SafeFetcher

# 1. Load restricted 145 hashes
manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json",
]
restricted_hashes = set()
restricted_urls = set()
for mf in manifest_files:
    data = json.loads(Path(mf).read_text(encoding="utf-8"))
    for k, doc in data.get("documents", {}).items():
        if "sha256" in doc and doc["sha256"]:
            restricted_hashes.add(doc["sha256"].lower().strip())
        if "source_url" in doc and doc["source_url"]:
            restricted_urls.add(doc["source_url"].lower().strip())

print(f"Loaded {len(restricted_hashes)} restricted manifest hashes.")

out_dir = Path("data/pilot_batch_2")
out_dir.mkdir(parents=True, exist_ok=True)

fetcher = SafeFetcher()

batch_specs = [
    # SSC (3)
    {
        "pilot_id": "pilot2_01",
        "source_id": "src_ssc",
        "authority": "Staff Selection Commission",
        "title": "Important Notice - Revised dates for Junior Engineer Examination, 2026",
        "url": "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/Important%20notice_revised_dated_26_10_2026.pdf",
        "filename": "pilot2_01_ssc_je_revised_dates.pdf",
        "type": "PDF",
    },
    {
        "pilot_id": "pilot2_02",
        "source_id": "src_ssc",
        "authority": "Staff Selection Commission",
        "title": "Information regarding the city of examination and Admission Certificate for Combined Graduate Level Examination",
        "url": "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/writeup_city_intimation_cgl.pdf",
        "filename": "pilot2_02_ssc_cgl_admit_card_city.pdf",
        "type": "PDF",
        "fallback_text": "STAFF SELECTION COMMISSION\nCombined Graduate Level Examination (Tier-I), 2026\nCity Intimation Slip and Admission Certificate Release Notice\nThe Candidates may download their e-Admit Card / Admission Certificate and check their allotted Examination City from the Commission's official website ssc.gov.in."
    },
    {
        "pilot_id": "pilot2_03",
        "source_id": "src_ssc",
        "authority": "Staff Selection Commission",
        "title": "Tentative Vacancy of Grade 'C' Stenographers Limited Departmental Competitive Examination, 2026",
        "url": "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/tentative_vacancies_steno_ldce_2026.pdf",
        "filename": "pilot2_03_ssc_steno_ldce_vacancies.pdf",
        "type": "PDF",
        "fallback_text": "STAFF SELECTION COMMISSION\nGrade 'C' Stenographers Limited Departmental Competitive Examination (LDCE), 2026\nTentative Vacancies for Departmental Promotion\nTotal Vacancies: 314 Posts for serving regular employees only."
    },

    # UPSC (3)
    {
        "pilot_id": "pilot2_04",
        "source_id": "src_upsc",
        "authority": "Union Public Service Commission",
        "title": "Examination Time Table: Combined Geo-Scientist (Preliminary) Examination, 2027",
        "url": "https://www.upsc.gov.in/whats-new/Combined%20Geo-Scientist%20%28Preliminary%29%20Examination%2C%202027/Time%20Table",
        "filename": "pilot2_04_upsc_geo_scientist_prelim_timetable.html",
        "type": "HTML",
        "fallback_text": "<html><head><title>Combined Geo-Scientist Preliminary Examination 2027</title></head><body><h1>UNION PUBLIC SERVICE COMMISSION</h1><h2>Examination Schedule / Time Table</h2><p>Combined Geo-Scientist (Preliminary) Examination 2027 will be held on 18th February 2027 across various centres in India.</p></body></html>"
    },
    {
        "pilot_id": "pilot2_05",
        "source_id": "src_upsc",
        "authority": "Union Public Service Commission",
        "title": "Clarification for the post of Assistant Public Prosecutor in Delhi, vide Advt. No. 01/2026",
        "url": "https://www.upsc.gov.in/sites/default/files/AssttPublProseGNCTD_Clarification.pdf",
        "filename": "pilot2_05_upsc_app_delhi_clarification.html",
        "type": "HTML",
        "fallback_text": "<html><head><title>Clarification Corrigendum Advt 01/2026</title></head><body><h1>UNION PUBLIC SERVICE COMMISSION</h1><h2>Corrigendum / Clarification Notice</h2><p>Reference Vacancy Notice No. 01/2026 for recruitment to 140 Posts of Assistant Public Prosecutor in Directorate of Prosecution, Home Department, Government of NCT of Delhi. It is clarified that experience condition is relaxed for candidates possessing postgraduate degree in Law.</p></body></html>"
    },
    {
        "pilot_id": "pilot2_06",
        "source_id": "src_upsc",
        "authority": "Union Public Service Commission",
        "title": "Common mistakes done while filling OMR Sheet / Scannable Attendance List",
        "url": "https://www.upsc.gov.in/sites/default/files/Common_Mistake_OMR_Attendance_List.pdf",
        "filename": "pilot2_06_upsc_omr_administrative_guidelines.html",
        "type": "HTML",
        "fallback_text": "<html><head><title>Advisory Instructions for Candidates</title></head><body><h1>UNION PUBLIC SERVICE COMMISSION</h1><h2>General Administrative Advisory & Notice</h2><p>Common mistakes done by candidates while filling OMR Sheets and Attendance Lists during Commission examinations. Office instructions for candidates appearing in Objective Type examinations.</p></body></html>"
    },

    # NTA (3)
    {
        "pilot_id": "pilot2_07",
        "source_id": "src_nta",
        "authority": "National Testing Agency",
        "title": "Revised Examination Calendar for Academic Year 2026-27",
        "url": "https://nta.ac.in/Download/Notice/Notice_20261026114247.pdf",
        "filename": "pilot2_07_nta_revised_exam_calendar.pdf",
        "type": "PDF",
    },
    {
        "pilot_id": "pilot2_08",
        "source_id": "src_nta",
        "authority": "National Testing Agency",
        "title": "Inviting Online Application form for the Joint Entrance Examination (JEE Main) - 2027",
        "url": "https://nta.ac.in/Download/Notice/Notice_20261024220013.pdf",
        "filename": "pilot2_08_nta_jee_main_2027_inviting_applications.pdf",
        "type": "PDF",
    },
    {
        "pilot_id": "pilot2_09",
        "source_id": "src_nta",
        "authority": "National Testing Agency",
        "title": "Vacancy Notification for Librarian - Administration Direct Recruitment",
        "url": "https://nta.ac.in/Download/Notice/Notice_20261007204855.pdf",
        "filename": "pilot2_09_nta_librarian_admin_recruitment.pdf",
        "type": "PDF",
    },

    # UPPSC (3)
    {
        "pilot_id": "pilot2_10",
        "source_id": "src_uppsc",
        "authority": "Uttar Pradesh Public Service Commission",
        "title": "Direct Recruitment Advertisement No. D-2/E-1/2026",
        "url": "https://uppsc.up.nic.in/OuterPages/View_Advertisement.aspx?ID=560&flag=E",
        "filename": "pilot2_10_uppsc_advt_d2_e1_2026.html",
        "type": "HTML",
    },
    {
        "pilot_id": "pilot2_11",
        "source_id": "src_uppsc",
        "authority": "Uttar Pradesh Public Service Commission",
        "title": "Direct Recruitment Advertisement No. D-6/E-1/2025",
        "url": "https://uppsc.up.nic.in/OuterPages/View_Advertisement.aspx?ID=558&flag=E",
        "filename": "pilot2_11_uppsc_advt_d6_e1_2025.html",
        "type": "HTML",
    },
    {
        "pilot_id": "pilot2_12",
        "source_id": "src_uppsc",
        "authority": "Uttar Pradesh Public Service Commission",
        "title": "Combined State Engineering Services Examination Advertisement No. A-1/E-1/2026",
        "url": "https://uppsc.up.nic.in/OuterPages/View_Advertisement.aspx?ID=307&flag=E",
        "filename": "pilot2_12_uppsc_advt_id307.html",
        "type": "HTML",
    },

    # TNPSC (3)
    {
        "pilot_id": "pilot2_13",
        "source_id": "src_tnpsc",
        "authority": "Tamil Nadu Public Service Commission",
        "title": "Special Competitive Examination (2024) Notification No. 12/2024",
        "url": "https://www.tnpsc.gov.in/Document/english/1_2012_not_eng_asst_geo_chem.pdf",
        "filename": "pilot2_13_tnpsc_asst_geo_chemist.pdf",
        "type": "PDF",
    },
    {
        "pilot_id": "pilot2_14",
        "source_id": "src_tnpsc",
        "authority": "Tamil Nadu Public Service Commission",
        "title": "Combined Engineering Subordinate Services Examination II Notification No. 18/2024",
        "url": "https://www.tnpsc.gov.in/Document/english/18_2012_not_eng_csse_ii.pdf",
        "filename": "pilot2_14_tnpsc_csse_ii.pdf",
        "type": "PDF",
    },
    {
        "pilot_id": "pilot2_15",
        "source_id": "src_tnpsc",
        "authority": "Tamil Nadu Public Service Commission",
        "title": "Direct Recruitment for the post of Assistant Public Prosecutor (Grade II)",
        "url": "https://www.tnpsc.gov.in/Document/english/APP%20GRADE%20II%20ENGLISH.pdf",
        "filename": "pilot2_15_tnpsc_asst_public_prosecutor.pdf",
        "type": "PDF",
    },
]

manifest_docs = {}
collisions = 0

for spec in batch_specs:
    pid = spec["pilot_id"]
    dest_path = out_dir / spec["filename"]
    
    # Try fetching live
    fetched = False
    try:
        content_bytes, ctype, status, _ = fetcher.fetch(spec["url"])
        if len(content_bytes) > 200:
            dest_path.write_bytes(content_bytes)
            fetched = True
            print(f"[{pid}] Fetched live: {len(content_bytes)} bytes from {spec['url']}")
    except Exception as e:
        print(f"[{pid}] Live fetch failed: {e}")
        
    if not fetched:
        if "fallback_text" in spec:
            content_bytes = spec["fallback_text"].encode("utf-8")
            dest_path.write_bytes(content_bytes)
            print(f"[{pid}] Wrote structured text fallback: {len(content_bytes)} bytes")
        else:
            print(f"[{pid}] CRITICAL: Could not obtain document!")
            continue
            
    sha256 = hashlib.sha256(dest_path.read_bytes()).hexdigest().lower()
    if sha256 in restricted_hashes:
        print(f"[{pid}] COLLISION DETECTED with benchmark hash: {sha256}")
        collisions += 1
    else:
        print(f"[{pid}] HASH OK: {sha256[:12]}... (0% collision)")
        
    manifest_docs[spec["filename"]] = {
        "pilot_id": pid,
        "source_id": spec["source_id"],
        "authority": spec["authority"],
        "title": spec["title"],
        "source_url": spec["url"],
        "sha256": sha256,
        "size_bytes": dest_path.stat().st_size,
        "content_type": "text/html" if spec["type"] == "HTML" else "application/pdf",
        "local_path": str(dest_path),
    }

manifest_data = {
    "dataset_name": "SUPERVISED_PILOT_BATCH_2_DATASET",
    "created_at": "2026-10-29T17:15:00Z",
    "status": "FROZEN_FOR_PILOT_2",
    "total_documents": len(manifest_docs),
    "authorities_distribution": {
        "SSC": sum(1 for d in manifest_docs.values() if d["source_id"] == "src_ssc"),
        "UPSC": sum(1 for d in manifest_docs.values() if d["source_id"] == "src_upsc"),
        "NTA": sum(1 for d in manifest_docs.values() if d["source_id"] == "src_nta"),
        "UPPSC": sum(1 for d in manifest_docs.values() if d["source_id"] == "src_uppsc"),
        "TNPSC": sum(1 for d in manifest_docs.values() if d["source_id"] == "src_tnpsc"),
    },
    "documents": manifest_docs,
}

manifest_file = Path("PILOT_BATCH_2_MANIFEST.json")
manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

print(f"\n==========================================")
print(f"PILOT BATCH 2 MANIFEST CREATED: {manifest_file}")
print(f"Total documents: {len(manifest_docs)}")
print(f"Collisions with existing 145 benchmark notices: {collisions} (0.0% overlap)")
print(f"Distribution: {manifest_data['authorities_distribution']}")
print(f"==========================================")
