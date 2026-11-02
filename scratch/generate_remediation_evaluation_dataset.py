import os
import json
import hashlib
from pathlib import Path
import fitz  # PyMuPDF

os.makedirs("data/remediation_evaluation_notices", exist_ok=True)

notices_data = [
    {
        "filename": "rem_01_ssc_cgl_schedule.pdf",
        "format": "pdf",
        "authority": "Staff Selection Commission",
        "source_id": "src_ssc",
        "title": "Important Notice: Schedule of Combined Graduate Level Examination (Tier-II), 2026",
        "url": "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/schedule_cgl_tier2_2026.pdf",
        "text": """STAFF SELECTION COMMISSION
NOTICE
F.No. 4/1/2026-C-1/1

The Commission has decided to conduct the Combined Graduate Level Examination (Tier-II), 2026 as per the given schedule:

Schedule of Examination: 18th to 20th January 2027

The candidates are advised to visit the website of the Commission at regular intervals for updates.
The Admission Certificate (e-Admit Card) of the candidates will be uploaded on the website of the respective Regional Offices of the Commission about one week before the conduct of the examination.

Under Secretary (C-1)
Staff Selection Commission
Dated: 05.11.2026
"""
    },
    {
        "filename": "rem_02_ssc_stenographer_recruitment.pdf",
        "format": "pdf",
        "authority": "Staff Selection Commission",
        "source_id": "src_ssc",
        "title": "Notice of Examination for Stenographer Grade 'C' & 'D' Examination, 2026",
        "url": "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/stenographer_cd_2026.pdf",
        "text": """STAFF SELECTION COMMISSION
NOTICE
Stenographer Grade 'C' & 'D' Examination, 2026
F.No. 2/3/2026-P&P-II

Dates for submission of online applications: 05.12.2026 to 04.01.2027
Last date and time for receipt of online applications: 04.01.2027 (23:00 hours)
Schedule of Computer Based Examination: February, 2027

Vacancies:
Total tentative vacancies: 1245 posts in various Ministries and Departments.

Age Limit:
A candidate must be between 18 to 27 years of age as on 01.08.2026.

Qualifications:
Candidates must have passed 12th Standard or equivalent examination from a recognized Board or University.
"""
    },
    {
        "filename": "rem_03_ssc_constable_gd_corrigendum.pdf",
        "format": "pdf",
        "authority": "Staff Selection Commission",
        "source_id": "src_ssc",
        "title": "Corrigendum to Constable (GD) in Central Armed Police Forces Examination, 2026",
        "url": "https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/corrigendum_constable_gd_2026.pdf",
        "text": """STAFF SELECTION COMMISSION
CORRIGENDUM
F.No. 3/1/2026-P&P-I

Candidates may refer to the Notice of Constable (GD) in Central Armed Police Forces Examination, 2026 published on the Commission's website.

1. Total vacancies are revised from 24000 to 26146 posts.
2. Revised examination schedule: 12th to 25th March 2027.

All other terms and conditions of the Notice will remain unchanged.

Under Secretary
Staff Selection Commission
"""
    },
    {
        "filename": "rem_04_upsc_medical_officer_recruitment.html",
        "format": "html",
        "authority": "Union Public Service Commission",
        "source_id": "src_upsc",
        "title": "Special Advertisement No. 51/2026: Recruitment to 215 Posts of Medical Officer (General Duty)",
        "url": "https://upsc.gov.in/recruitment/special-advt-51-2026-medical-officer",
        "text": """<!DOCTYPE html>
<html>
<head><title>Special Advertisement No. 51/2026</title></head>
<body>
<h1>UNION PUBLIC SERVICE COMMISSION</h1>
<h2>Advertisement No. 51/2026</h2>
<p>Online Recruitment Applications (ORA) are invited for direct recruitment by selection to 215 Posts of Medical Officer (General Duty Medical Officer) in Ministry of Health and Family Welfare.</p>
<p>Opening date for submission of online application: 10.12.2026.</p>
<p>Closing date for submission of online application: 09.01.2027.</p>
<p>Age limit: Not exceeding 35 years as on normal closing date.</p>
<p>Qualifications: A recognized MBBS degree qualification included in the First Schedule or Second Schedule or Part II of the Third Schedule to the Indian Medical Council Act, 1956.</p>
<p>Total vacancies: 215 posts (UR-95, OBC-58, SC-32, ST-15, EWS-15).</p>
</body>
</html>
"""
    },
    {
        "filename": "rem_05_upsc_civil_services_main_schedule.html",
        "format": "html",
        "authority": "Union Public Service Commission",
        "source_id": "src_upsc",
        "title": "Timetable and Schedule for Civil Services (Main) Examination, 2026",
        "url": "https://upsc.gov.in/examinations/timetable-schedule-csm-2026",
        "text": """<!DOCTYPE html>
<html>
<head><title>Timetable and Schedule for Civil Services (Main) Examination, 2026</title></head>
<body>
<h1>UNION PUBLIC SERVICE COMMISSION</h1>
<h2>Notice: Timetable for Civil Services (Main) Examination 2026</h2>
<p>F.1/8/2026-E.I(B)</p>
<p>Union Public Service Commission will conduct the Civil Services (Main) Examination 2026 commencing from 22nd January 2027.</p>
<p>The Examination will be held on 22nd, 23rd, 24th, 29th and 30th January 2027 in two sessions (9:00 AM to 12:00 Noon and 2:00 PM to 5:00 PM).</p>
<p>The e-Admit Cards for the candidates will be uploaded on the Commission's website 3 weeks before the date of commencement of the examination.</p>
</body>
</html>
"""
    },
    {
        "filename": "rem_06_upsc_assistant_director_corrigendum.html",
        "format": "html",
        "authority": "Union Public Service Commission",
        "source_id": "src_upsc",
        "title": "Addendum to Advertisement No. 12/2026 for Recruitment to the Post of Assistant Director (Law)",
        "url": "https://upsc.gov.in/recruitment/addendum-advt-12-2026-law",
        "text": """<!DOCTYPE html>
<html>
<head><title>Addendum to Advertisement No. 12/2026</title></head>
<body>
<h1>UNION PUBLIC SERVICE COMMISSION</h1>
<h2>Addendum Notice</h2>
<p>Reference Advertisement No. 12/2026 published by the Commission for recruitment to 18 Posts of Assistant Director (Law).</p>
<p>Total Vacancies: 18 posts.</p>
<p>Essential Qualification is amended as under: Degree in Law (LLB) of a recognized University with minimum 2 years experience in legal affairs.</p>
<p>The closing date for submission of online application is extended to 15.01.2027.</p>
</body>
</html>
"""
    },
    {
        "filename": "rem_07_nta_swayam_july_semester_exam.pdf",
        "format": "pdf",
        "authority": "National Testing Agency",
        "source_id": "src_nta",
        "title": "Public Notice: Schedule for Study Webs of Active-Learning for Young Aspiring Minds (SWAYAM) July 2026 Semester",
        "url": "https://nta.ac.in/notice/swayam_july_2026_exam_schedule.pdf",
        "text": """NATIONAL TESTING AGENCY
PUBLIC NOTICE
Dated: 08.11.2026
NTA/SWAYAM/2026/02

Subject: Schedule and Online Applications for SWAYAM July 2026 Semester Courses Examination

National Testing Agency will be conducting the SWAYAM July 2026 Semester Examination for certification across India.
Dates for submission of online applications: 10.11.2026 to 10.12.2026
Dates of Examination: 20 and 21 February 2027
Eligibility: Students enrolled in certificate, diploma or degree programs across UGC/AICTE recognized universities.
The Admit Cards will be available for downloading 10 days before the examination from the official portal.
"""
    },
    {
        "filename": "rem_08_nta_csir_net_exam_dates.pdf",
        "format": "pdf",
        "authority": "National Testing Agency",
        "source_id": "src_nta",
        "title": "Public Notice: Advance Intimation of Examination Schedule for Joint CSIR-UGC NET December 2026",
        "url": "https://nta.ac.in/notice/csir_net_dec_2026_exam_dates.pdf",
        "text": """NATIONAL TESTING AGENCY
PUBLIC NOTICE
NTA/CSIR-NET/2026/03
Dated: 12.11.2026

Subject: Examination Schedule for Joint CSIR-UGC NET Examination December 2026

The National Testing Agency announces the Examination Schedule for Joint CSIR-UGC NET December 2026.
The Examination will be held on 28th February 2027 and 01st March 2027 in Computer Based Test (CBT) mode.
The City Intimation Slip and Admit Cards will be released on nta.ac.in three days prior to the date of examination.
"""
    },
    {
        "filename": "rem_09_nta_neet_ss_eligibility_notice.pdf",
        "format": "pdf",
        "authority": "National Testing Agency",
        "source_id": "src_nta",
        "title": "Information Bulletin and Application for National Eligibility cum Entrance Test (NEET-SS) 2026",
        "url": "https://nta.ac.in/notice/neet_ss_2026_information_bulletin.pdf",
        "text": """NATIONAL TESTING AGENCY
NOTICE
NTA/NEET-SS/2026/01

Subject: Inviting Online Applications for Admissions to DM/MCh Super Specialty Courses (NEET-SS) 2026

National Testing Agency invites online applications for admissions into Super Specialty Medical Courses.
Dates for submission of online applications: 01.12.2026 to 31.12.2026
Date of Examination: 15.03.2027
Eligibility: Candidates must possess recognized MD/MS/DNB degree or equivalent in the relevant specialty from NMC recognized medical college.
"""
    },
    {
        "filename": "rem_10_uppsc_ayush_medical_officer.html",
        "format": "html",
        "authority": "Uttar Pradesh Public Service Commission",
        "source_id": "src_uppsc",
        "title": "Direct Recruitment Advertisement No. 04/2026: Medical Officer (Ayurvedic & Unani)",
        "url": "https://uppsc.up.nic.in/recruitment/advt-04-2026-medical-officer",
        "text": """<!DOCTYPE html>
<html>
<head><title>Direct Recruitment Advertisement No. 04/2026</title></head>
<body>
<h1>UTTAR PRADESH PUBLIC SERVICE COMMISSION</h1>
<h2>Advertisement No. 04/2026</h2>
<p>Online applications are invited for recruitment to 425 posts of Medical Officer in Department of Ayush.</p>
<p>Total vacancies: 425 posts.</p>
<p>Online Application Starts: 01.12.2026.</p>
<p>Last Date for Submission: 02.01.2027.</p>
<p>Age limit: 21 to 40 years as on July 1, 2026.</p>
<p>Qualifications: A degree in Ayurvedic or Unani Tibb of a recognized University or Board.</p>
<p>Date of Screening Examination: 25 April 2027 from 11:00 AM to 1:00 PM.</p>
</body>
</html>
"""
    },
    {
        "filename": "rem_11_uppsc_technical_education_schedule.html",
        "format": "html",
        "authority": "Uttar Pradesh Public Service Commission",
        "source_id": "src_uppsc",
        "title": "Examination Schedule for UP Technical Education (Teaching) Service Examination",
        "url": "https://uppsc.up.nic.in/notices/technical-education-exam-schedule-2026",
        "text": """<!DOCTYPE html>
<html>
<head><title>Examination Schedule for Technical Education Service</title></head>
<body>
<h1>UTTAR PRADESH PUBLIC SERVICE COMMISSION</h1>
<h2>Notice No. 58/E-3/2026</h2>
<p>Notice regarding Examination Schedule for Technical Education (Teaching) Service Examination 2026.</p>
<p>The Examination will be held on 14th March 2027 in two shifts (9:30 AM to 12:00 PM and 2:00 PM to 4:30 PM).</p>
<p>Candidates can download their Admit Card from the Commission's website 10 days before the exam date.</p>
</body>
</html>
"""
    },
    {
        "filename": "rem_12_uppsc_assistant_conservator_corrigendum.html",
        "format": "html",
        "authority": "Uttar Pradesh Public Service Commission",
        "source_id": "src_uppsc",
        "title": "Corrigendum to Assistant Conservator of Forest / Range Forest Officer Examination 2026",
        "url": "https://uppsc.up.nic.in/notices/corrigendum-acf-rfo-2026",
        "text": """<!DOCTYPE html>
<html>
<head><title>Corrigendum Notice</title></head>
<body>
<h1>UTTAR PRADESH PUBLIC SERVICE COMMISSION</h1>
<h2>Advt. No. A-2/E-1/2026 Corrigendum</h2>
<p>With reference to Advertisement No. A-2/E-1/2026 for ACF/RFO Examination 2026.</p>
<p>Total vacancies are enhanced from 45 to 62 posts.</p>
<p>The last date for submission of online application is extended to 10.01.2027.</p>
<p>All other conditions of the original advertisement remain unaltered.</p>
</body>
</html>
"""
    },
    {
        "filename": "rem_13_tnpsc_group_i_recruitment.pdf",
        "format": "pdf",
        "authority": "Tamil Nadu Public Service Commission",
        "source_id": "src_tnpsc",
        "title": "Combined Civil Services Examination I (Group I Services) Notification No. 12/2026",
        "url": "https://www.tnpsc.gov.in/document/notification/group_1_services_2026.pdf",
        "text": """TAMIL NADU PUBLIC SERVICE COMMISSION
NOTIFICATION NO. 12/2026
DATED: 10.12.2026

Applications are invited online from 10.12.2026 to 09.01.2027 for direct recruitment to the posts included in Combined Civil Services Examination I (Group I Services).

Total number of vacancies: 148 posts.

Age Limit:
A candidate must have attained the age of 21 years and must not have crossed the age of 34 years as on 01.07.2026.

Qualifications:
Must possess a Bachelor's Degree of any University recognized by the University Grants Commission.

Date of Preliminary Examination: 12.04.2027 (9:30 AM to 12:30 PM).
"""
    },
    {
        "filename": "rem_14_tnpsc_group_i_hall_ticket_admit.pdf",
        "format": "pdf",
        "authority": "Tamil Nadu Public Service Commission",
        "source_id": "src_tnpsc",
        "title": "Press Release: Release of Hall Ticket / Admit Card for Combined Civil Services Examination I",
        "url": "https://www.tnpsc.gov.in/document/pressrelease/hall_ticket_group_1_2026.pdf",
        "text": """TAMIL NADU PUBLIC SERVICE COMMISSION
PRESS RELEASE NO. 62/2026
DATED: 28.03.2027

Subject: Release of Hall Ticket / Admit Card for Combined Civil Services Examination I

The Tamil Nadu Public Service Commission has uploaded the Memorandum of Admission (Hall Tickets / Admit Cards) for the candidates admitted to the Preliminary Examination for Combined Civil Services Examination I on its official website www.tnpsc.gov.in.
Candidates can download the Hall Ticket by entering their Application Number and Date of Birth. No individual hall tickets will be sent by post.

Controller of Examinations
"""
    },
    {
        "filename": "rem_15_tnpsc_departmental_promotion_circular.pdf",
        "format": "pdf",
        "authority": "Tamil Nadu Public Service Commission",
        "source_id": "src_tnpsc",
        "title": "Internal Circular: Limited Departmental Competitive Examination (LDCE) for Section Officers",
        "url": "https://www.tnpsc.gov.in/document/circular/ldce_section_officers_2026.pdf",
        "text": """TAMIL NADU PUBLIC SERVICE COMMISSION
INTERNAL CIRCULAR NO. 18/LDCE/2026
DATED: 15.11.2026

Subject: Limited Departmental Competitive Examination (LDCE) 2026 for Promotion to Section Officer

Tamil Nadu Public Service Commission announces the Limited Departmental Competitive Examination (LDCE) 2026 for departmental promotion of serving staff to the post of Section Officer.
Only departmental candidates serving regularly for not less than 5 years in the Commission are eligible.
Last date for receipt of application through proper channel is 15.01.2027.
This circular is for internal departmental circulation only.

Secretary
"""
    }
]

manifest = {
    "dataset_name": "REMEDIATION_EVALUATION_DATASET",
    "created_at": "2026-11-02T11:00:00Z",
    "status": "FROZEN_FOR_POST_REMEDIATION_EVALUATION",
    "total_documents": len(notices_data),
    "authorities_distribution": {
        "SSC": 3,
        "UPSC": 3,
        "NTA": 3,
        "UPPSC": 3,
        "TNPSC": 3
    },
    "documents": {}
}

for item in notices_data:
    fname = item["filename"]
    fpath = Path("data/remediation_evaluation_notices") / fname
    if item["format"] == "pdf":
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 72), item["text"], fontsize=11, fontname="helv")
        doc.save(str(fpath))
        doc.close()
    else:
        fpath.write_text(item["text"], encoding="utf-8")
    
    file_bytes = fpath.read_bytes()
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    manifest["documents"][fname] = {
        "audit_id": fname.split("_")[0] + "_" + fname.split("_")[1],
        "source_id": item["source_id"],
        "authority": item["authority"],
        "title": item["title"],
        "source_url": item["url"],
        "sha256": sha256,
        "size_bytes": len(file_bytes),
        "content_type": "application/pdf" if item["format"] == "pdf" else "text/html",
        "local_path": str(fpath)
    }

manifest_path = Path("REMEDIATION_EVALUATION_MANIFEST.json")
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Generated {len(notices_data)} remediation evaluation documents and saved manifest to {manifest_path}")
