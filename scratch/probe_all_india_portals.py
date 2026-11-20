import httpx
from testkart_intelligence.discovery.parser import ListingParser

CANDIDATE_PORTALS = [
    # Central
    ("UPSC", "Union Public Service Commission", "Central", "Central", "https://www.upsc.gov.in/whats-new"),
    ("SSC", "Staff Selection Commission", "Central", "Central", "https://ssc.gov.in/api/general-website/portal/notice-boards?page=1&limit=20&contentType=notice-boards&key=createdAt&order=DESC&isAttachment=true&language=english&attributes=id,headline,examId,contentType,redirectUrl,startDate,endDate,language,createdAt"),
    ("ISRO", "Indian Space Research Organisation", "Central", "Central", "https://www.isro.gov.in/Careers.html"),
    ("DRDO", "Defence Research and Development Organisation", "Defence", "Central", "https://www.drdo.gov.in/drdo/careers"),
    ("ESIC", "Employees State Insurance Corporation", "Central", "Central", "https://www.esic.gov.in/recruitments"),
    ("EPFO", "Employees Provident Fund Organisation", "Central", "Central", "https://www.epfindia.gov.in/site_en/Recruitments.php"),
    ("IBPS", "Institute of Banking Personnel Selection", "Banking", "Central", "https://www.ibps.in/"),
    ("RRB_CHD", "Railway Recruitment Board (Chandigarh)", "Railway", "Central", "https://www.rrbcdg.gov.in/"),
    ("RRB_MUM", "Railway Recruitment Board (Mumbai)", "Railway", "Maharashtra", "https://www.rrbmumbai.gov.in/"),
    # North India
    ("UPPSC", "Uttar Pradesh Public Service Commission", "PSC", "Uttar Pradesh", "https://uppsc.up.nic.in/CandidatePages/Notifications.aspx"),
    ("UPSSSC", "UP Subordinate Services Selection Commission", "Subordinate Services", "Uttar Pradesh", "https://upsssc.gov.in/AllNotifications.aspx"),
    ("DSSSB", "Delhi Subordinate Services Selection Board", "Subordinate Services", "Delhi", "https://dsssb.delhi.gov.in/notifications"),
    ("RPSC", "Rajasthan Public Service Commission", "PSC", "Rajasthan", "https://rpsc.rajasthan.gov.in/advertisements"),
    ("RSSB", "Rajasthan Staff Selection Board", "Subordinate Services", "Rajasthan", "https://rssb.rajasthan.gov.in/advertisements"),
    ("HPSC", "Haryana Public Service Commission", "PSC", "Haryana", "https://hpsc.gov.in/en-us/Instructions"),
    ("HSSC", "Haryana Staff Selection Commission", "Subordinate Services", "Haryana", "https://hssc.gov.in/Advertisements"),
    ("UKPSC", "Uttarakhand Public Service Commission", "PSC", "Uttarakhand", "https://psc.uk.gov.in/candidate-corner/recruitment"),
    ("HPPSC", "Himachal Pradesh Public Service Commission", "PSC", "Himachal Pradesh", "https://www.hppsc.hp.gov.in/hppsc/"),
    ("JKSSB", "Jammu & Kashmir Services Selection Board", "Subordinate Services", "Jammu & Kashmir", "https://jkssb.nic.in/"),
    ("PPSC", "Punjab Public Service Commission", "PSC", "Punjab", "https://ppsc.gov.in/"),
    # West & Central India
    ("MPSC", "Maharashtra Public Service Commission", "PSC", "Maharashtra", "https://mpsc.gov.in/adv_notification/8"),
    ("GPSC", "Gujarat Public Service Commission", "PSC", "Gujarat", "https://gpsc.gujarat.gov.in/advertisements"),
    ("MPPSC", "Madhya Pradesh Public Service Commission", "PSC", "Madhya Pradesh", "https://mppsc.mp.gov.in/advertisement"),
    ("CGPSC", "Chhattisgarh Public Service Commission", "PSC", "Chhattisgarh", "https://psc.cg.gov.in/htm/Advertisement.htm"),
    # South India
    ("APPSC", "Andhra Pradesh Public Service Commission", "PSC", "Andhra Pradesh", "https://portal-psc.ap.gov.in/HomePages/RecruitmentNotifications"),
    ("TNPSC", "Tamil Nadu Public Service Commission", "PSC", "Tamil Nadu", "https://www.tnpsc.gov.in/English/notification.aspx"),
    ("KPSC", "Karnataka Public Service Commission", "PSC", "Karnataka", "https://kpsc.kar.nic.in/"),
    ("KERALA_PSC", "Kerala Public Service Commission", "PSC", "Kerala", "https://www.keralapsc.gov.in/notifications"),
    ("TGPSC", "Telangana Public Service Commission", "PSC", "Telangana", "https://www.tspsc.gov.in/"),
    # East & North-East India
    ("BPSC", "Bihar Public Service Commission", "PSC", "Bihar", "https://bpsc.bihar.gov.in/"),
    ("WBPSC", "West Bengal Public Service Commission", "PSC", "West Bengal", "https://psc.wb.gov.in/"),
    ("OSSC", "Odisha Staff Selection Commission", "Subordinate Services", "Odisha", "https://www.ossc.gov.in/Public/OSSC/Default.aspx"),
    ("JPSC", "Jharkhand Public Service Commission", "PSC", "Jharkhand", "https://www.jpsc.gov.in/"),
    ("APSC", "Assam Public Service Commission", "PSC", "Assam", "https://apsc.nic.in/advt_2026.asp"),
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}

for code, name, cat, state, url in CANDIDATE_PORTALS:
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            r = client.get(url)
            cands = ListingParser.parse_listing(r.text, str(r.url)) if r.status_code == 200 else []
            print(f"[OK] {code:<11} | HTTP {r.status_code} | {state:<16} | Candidates: {len(cands):<4} | {str(r.url)[:65]}", flush=True)
    except Exception as exc:
        print(f"[FAIL] {code:<9} | {state:<16} | {type(exc).__name__}: {str(exc)[:60]}", flush=True)
