"""Build and curate the local 22 real official notice validation dataset."""

import os
import hashlib
from datetime import datetime, timezone
import httpx
import urllib.request
import ssl

OUTPUT_DIR = "data/validation_notices"
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf,*/*;q=0.8",
}

def save_from_url(url: str, filename: str, referer: str = None) -> dict:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    filepath = os.path.join(OUTPUT_DIR, filename)

    if "kpsc.kar" in url or "kpsc.karnataka" in url:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            content = resp.read()
            final_url = resp.geturl()
    else:
        with httpx.Client(verify=False, timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            content = resp.content
            final_url = str(resp.url)

    with open(filepath, "wb") as f:
        f.write(content)

    sha = hashlib.sha256(content).hexdigest()
    return {
        "filename": filename,
        "filepath": filepath,
        "url": final_url,
        "sha256": sha,
        "size": len(content),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

DOWNLOAD_TARGETS = [
    # SSC Notices (Real Official Documents from ssc.gov.in)
    ("https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/JE_2026_City_Live_Notice_23102026.pdf", "notice_01_ssc_je_admit_card_city.pdf", "https://ssc.gov.in/notice-board"),
    ("https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/tentative_vacancies_24102026.pdf", "notice_02_ssc_stenographer_vacancies.pdf", "https://ssc.gov.in/notice-board"),
    ("https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/writeup_23102026.pdf", "notice_03_ssc_constable_gd_category_result.pdf", "https://ssc.gov.in/notice-board"),
    ("https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/writeup_12102026.pdf", "notice_04_ssc_constable_gd_pet_shortlist.pdf", "https://ssc.gov.in/notice-board"),
    ("https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/writeup_rhq.pdf", "notice_05_ssc_selection_posts_phase_xiv_key.pdf", "https://ssc.gov.in/notice-board"),
    ("https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/JE_Tentative_Vacancy_08102026.pdf", "notice_06_ssc_je_tentative_vacancy.pdf", "https://ssc.gov.in/notice-board"),

    # UPSC Notices (Real Official Documents from www.upsc.gov.in)
    ("https://www.upsc.gov.in/sites/default/files/NoticeCancellation-06-Posts-Advt-13-25-Engl-200826.pdf", "notice_07_upsc_cancellation_advt_13_2025.pdf", "https://www.upsc.gov.in/examinations/notifications"),
    ("https://www.upsc.gov.in/sites/default/files/AssttPublProseGNCTD-Notice-Engl-170926Rev.pdf", "notice_08_upsc_app_delhi_clarification.pdf", "https://www.upsc.gov.in/examinations/notifications"),
    ("https://www.upsc.gov.in/sites/default/files/Common_Mistake_OMR_SAL.pdf", "notice_09_upsc_omr_instructions.pdf", "https://www.upsc.gov.in/examinations/notifications"),
    ("https://www.upsc.gov.in/sites/default/files/Calendar-Year-2027-Engl-200526.pdf", "notice_10_upsc_annual_calendar_2027.pdf", "https://www.upsc.gov.in/examinations/exam-calendar"),
    ("https://www.upsc.gov.in/sites/default/files/Calendar-2026-Engl-150525_5.pdf", "notice_11_upsc_annual_calendar_2026.pdf", "https://www.upsc.gov.in/examinations/exam-calendar"),
    ("https://www.upsc.gov.in/sites/default/files/RevisedIIICalendar2025-Engl-160126.pdf", "notice_12_upsc_revised_calendar_2025.pdf", "https://www.upsc.gov.in/examinations/exam-calendar"),

    # NTA Notices (Real Official Documents from nta.ac.in & S3WaaS)
    ("https://nta.ac.in/Download/Notice/Notice_20261026114247.pdf", "notice_13_nta_revised_exam_calendar.pdf", "https://nta.ac.in/NoticeBoardArchive"),
    ("https://nta.ac.in/Download/Notice/Notice_20261024220013.pdf", "notice_14_nta_jee_main_inviting_application.pdf", "https://nta.ac.in/NoticeBoardArchive"),
    ("http://cdnbbsr.s3waas.gov.in/s301eee509ee2f68dc6014898c309e86bf/uploads/2026/10/202610161905649093.pdf", "notice_15_nta_corrigendum_ugc_net.pdf", "https://nta.ac.in/NoticeBoardArchive"),
    ("https://nta.ac.in/Download/Notice/Notice_20261016183525.pdf", "notice_16_nta_nift_inviting_application.pdf", "https://nta.ac.in/NoticeBoardArchive"),
    ("https://nta.ac.in/Download/Notice/Notice_20261009123259.pdf", "notice_17_nta_swayam_inviting_application.pdf", "https://nta.ac.in/NoticeBoardArchive"),
    ("https://nta.ac.in/Download/Notice/Notice_20261008212430.pdf", "notice_18_nta_portal_opening_extension.pdf", "https://nta.ac.in/NoticeBoardArchive"),
    ("https://nta.ac.in/Download/Notice/Notice_20261008083141.pdf", "notice_19_nta_joint_csir_ugc_net_application.pdf", "https://nta.ac.in/NoticeBoardArchive"),
    ("https://nta.ac.in/Download/Notice/Notice_20261007204855.pdf", "notice_20_nta_librarian_admin_recruitment.pdf", "https://nta.ac.in/NoticeBoardArchive"),

    # UPPSC Notice (Real Official Recruitment Document from uppsc.up.nic.in)
    ("https://uppsc.up.nic.in/OuterPages/View_Enclosure.aspx?ID=307&flag=E&FID=947", "notice_21_uppsc_samiksha_adhikari_recruitment.pdf", "https://uppsc.up.nic.in/CandidatePages/Notifications.aspx"),

    # KPSC Notice (Real Official Document from kpsc.karnataka.gov.in)
    ("https://kpsc.karnataka.gov.in/uploads/Secretary%20Information%20Instruction%20as%20on%2017-10-2026_1792235575.pdf", "notice_22_kpsc_secretary_instructions_notice.pdf", "https://kpsc.kar.nic.in"),
]

manifest = []
for url, fn, ref in DOWNLOAD_TARGETS:
    try:
        res = save_from_url(url, fn, referer=ref)
        manifest.append(res)
        print(f"Saved: {fn} ({res['size']} bytes, SHA: {res['sha256'][:10]}...)")
    except Exception as e:
        print(f"FAILED {fn}: {e}")

print(f"\nSuccessfully collected {len(manifest)} official notices into {OUTPUT_DIR}")
