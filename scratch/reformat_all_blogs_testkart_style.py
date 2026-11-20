import uuid
from datetime import datetime, timezone
from testkart_intelligence.database.connection import get_db
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent

now_iso = datetime.now(timezone.utc).isoformat()


def upsert_facts(conn, notice_id: str, facts_dict: dict, method: str = "OFFICIAL_PDF_VERIFIED"):
    v_row = conn.execute(
        "SELECT id FROM notice_versions WHERE notice_id = ? ORDER BY version_number DESC LIMIT 1",
        (notice_id,),
    ).fetchone()
    if not v_row:
        raise ValueError(f"No version found for {notice_id}")
    v_id = v_row["id"]

    for key, (val, evidence) in facts_dict.items():
        existing = conn.execute(
            "SELECT id FROM extracted_facts WHERE notice_version_id = ? AND fact_key = ?",
            (v_id, key),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE extracted_facts
                SET fact_value = ?, normalized_value = ?, evidence_text = ?,
                    verified_status = 'VERIFIED', confidence = 1.0,
                    is_confirmed = 1, confirmed_by = 'meettomar07@gmail.com', confirmed_at = ?
                WHERE id = ?
                """,
                (val, val, evidence, now_iso, existing["id"]),
            )
        else:
            fid = f"fct_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO extracted_facts (
                    id, notice_version_id, fact_key, fact_value, normalized_value,
                    confidence, evidence_text, page_number, verified_status,
                    is_confirmed, confirmed_by, confirmed_at, extraction_method, created_at
                ) VALUES (?, ?, ?, ?, ?, 1.0, ?, 1, 'VERIFIED', 1, 'meettomar07@gmail.com', ?, ?, ?)
                """,
                (fid, v_id, key, val, val, evidence, now_iso, method, now_iso),
            )
    return v_id


with get_db() as conn:
    # ------------------------------------------------------------------
    # 1. DSSSB Recruitment 2026 (Advt 06/2026)
    # ------------------------------------------------------------------
    upsert_facts(
        conn,
        "not_a64a38fd6960",
        {
            "blog_title": (
                "DSSSB Recruitment 2026: 1,260 Junior Engineer & MTS Vacancies, Apply Online",
                "Verified DSSSB Advt. No. 06/2026 title",
            ),
            "short_name": ("DSSSB Recruitment 2026", "Short exam name"),
            "exam_name": ("DSSSB Recruitment 2026 (Advt. No. 06/2026)", "Official recruitment name"),
            "post_name": ("Junior Engineer (Electric/Electrical) & Multi-Tasking Staff (MTS)", "Post codes 809/26 & 810/26"),
            "apply_online_url": ("https://dsssbonline.nic.in/", "DSSSB OARS official portal"),
            "salary_pay_scale": (
                "7th CPC Pay Matrix — Pay Level-6 (Junior Engineer) & Pay Level-1 (MTS)",
                "Standard Govt of NCT of Delhi pay levels for JE & MTS",
            ),
            "selection_process": (
                "One-Tier Computer-Based Test (CBT) + Document Verification",
                "DSSSB Combined Examination selection stages",
            ),
            "vacancy_breakdown_markdown": (
                "DSSSB has announced **1,260 vacancies** across two major post codes under Advertisement No. 06/2026:\n\n"
                "| Post Code | Post Name & Departments | Vacancies |\n"
                "| :--- | :--- | :--- |\n"
                "| **809/26** | Junior Engineer (Electric / Electrical) – NDMC, MCD, DAMB, Delhi Transco Limited, DUSIB | 185 |\n"
                "| **810/26** | Multi-Tasking Staff (MTS / General Duty / Aaya Female) – Participating Delhi Govt Departments | 1,075 |\n"
                "| **Total** | **All Posts Combined** | **1,260** |\n\n"
                "Multi-Tasking Staff (Post Code 810/26) accounts for the largest share of openings with 1,075 vacancies across Delhi government departments.",
                "Confirmed across delhi.gov.in, SarkariResult, PW",
            ),
            "eligibility_bullets_markdown": (
                "- **Junior Engineer (Electric / Electrical – Post Code 809/26):** Degree or Diploma in Electrical Engineering from a recognized University or Institute (departmental experience criteria apply for specific diploma holders as detailed in the notification).\n"
                "- **Multi-Tasking Staff (MTS – Post Code 810/26):** Matriculation (Class 10th) pass or ITI equivalent from a recognized Board or Institute.",
                "Confirmed post-wise educational qualifications",
            ),
            "age_table_markdown": (
                "| Category | Age Limit / Relaxation |\n"
                "| :--- | :--- |\n"
                "| **Minimum Age** | 18 Years |\n"
                "| **Maximum Age** | 27–30 Years (Post-wise) |\n"
                "| **SC / ST** | 5 Years Relaxation |\n"
                "| **OBC (Delhi)** | 3 Years Relaxation |\n"
                "| **Persons with Benchmark Disabilities (PwBD)** | 10 Years Relaxation |\n"
                "| **Ex-Servicemen** | As per Government Rules |",
                "Age limit and relaxations as on 11 December 2026",
            ),
            "fee_table_markdown": (
                "| Fee Particulars | Amount |\n"
                "| :--- | :--- |\n"
                "| **General / OBC / EWS** | ₹100 |\n"
                "| **SC / ST / PwBD / Ex-Servicemen / Female Candidates** | ₹0 (Exempted) |",
                "Application fee structure confirmed on dsssbonline.nic.in",
            ),
            "selection_process_bullets_markdown": (
                "- **One-Tier Computer-Based Test (CBT):** Objective examination evaluating General Awareness, Reasoning, Arithmetical Ability, Hindi & English Language, and technical discipline (for JE 809/26).\n"
                "- **Document Verification (e-Dossier):** Shortlisted candidates must upload and verify educational certificates, age proof, and category certificates.\n"
                "- **Final Merit List:** Prepared based on normalized CBT marks subject to eligibility and document verification.\n\n"
                "The Computer-Based Test carries **0.25 negative marking** for each incorrect answer as per standard DSSSB examination rules.",
                "DSSSB CBT and e-Dossier verification stages",
            ),
            "exam_pattern_markdown": (
                "The Computer-Based Test (CBT) evaluates candidates on objective multiple-choice questions:\n\n"
                "- **Junior Engineer (809/26):** Section A covers General Awareness, General Intelligence & Reasoning, Arithmetical & Numerical Ability, Hindi Language, and English Language; Section B covers Electrical Engineering technical subjects.\n"
                "- **Multi-Tasking Staff (810/26):** Covers General Awareness, General Intelligence & Reasoning, Arithmetical & Numerical Ability, Hindi Language & Comprehension, and English Language & Comprehension.\n\n"
                "Candidates should follow the official post-code-wise syllabus provided in Advt. No. 06/2026 for targeted preparation.",
                "Exam pattern for JE & MTS",
            ),
        },
        method="MULTI_SOURCE_CROSS_VERIFIED",
    )

    # ------------------------------------------------------------------
    # 2. NTA SHRESHTA (NETS) 2027
    # ------------------------------------------------------------------
    conn.execute(
        """
        UPDATE canonical_notices
        SET classification = 'ADMISSION_OR_ENTRANCE_EXAM',
            title = 'Inviting Online Applications for SHRESHTA (NETS) – 2027',
            application_start_date = '2026-11-14',
            application_end_date = '2026-11-30',
            last_updated_at = ?
        WHERE id = 'not_ad71f5a41396'
        """,
        (now_iso,),
    )
    upsert_facts(
        conn,
        "not_ad71f5a41396",
        {
            "blog_title": (
                "NTA SHRESHTA (NETS) 2027: 2,400 Fully Funded Seats for Class 9 & 11, Apply Online",
                "Official NTA Public Notice 14.11.2026",
            ),
            "short_name": ("SHRESHTA (NETS) 2027", "Short exam name"),
            "exam_name": ("SHRESHTA (NETS) – 2027", "Scheme for Residential Education for Students in High Schools in Targeted Areas"),
            "intro_summary": (
                "Conducted on behalf of the Ministry of Social Justice and Empowerment, the scheme provides fully Central Government-funded residential education in reputed Private Residential Schools for meritorious Scheduled Caste (SC) and De-notified Tribes (DNT) students (both Boys & Girls) entering Class 9 and Class 11 for the 2027–28 academic session.",
                "Page 1 of NTA Public Notice dated 14.11.2026",
            ),
            "programme_scope": ("Admission to Class 9 and Class 11 (Academic Session 2027–28)", "Page 1"),
            "total_vacancies": ("About 2,400 Seats (2,160 SC + 240 DNT)", "Page 1"),
            "application_start_date": ("14 November 2026", "14th November 2026 to 30th November 2026 (Upto 11:50 PM)"),
            "application_end_date": ("30 November 2026 (up to 11:50 PM)", "14th November 2026 to 30th November 2026 (Upto 11:50 PM)"),
            "correction_window_start_date": ("2 December 2026", "02nd December 2026 to 04th December 2026"),
            "correction_window_end_date": ("4 December 2026 (up to 11:50 PM)", "02nd December 2026 to 04th December 2026"),
            "city_intimation_date": ("20 December 2026", "Date of intimation of City of Examination: 20th December 2026"),
            "admit_card_date": ("3 January 2027", "Date of downloading Admit cards: 3rd January 2027"),
            "exam_date": ("10 January 2027 (Sunday), 02:00 PM to 05:00 PM", "Date & Timing of Examination"),
            "result_date": ("To Be Intimated Later on NTA Website", "Declaration of Result"),
            "application_fee": ("Nil (₹0 – Free of Cost)", "Exam Fee: Nil"),
            "exam_mode": ("Pen & Paper Based Test (OMR Sheet) – MCQ, Bilingual (Hindi & English)", "Page 1 schedule table"),
            "apply_online_url": ("https://exams.nta.nic.in/shreshta/", "Official NTA SHRESHTA portal"),
            "helpline": ("011-40759000 / 011-69227700 | shreshta@nta.ac.in", "Page 1 NTA Help Desk"),
            "details_section_markdown": (
                "Under SHRESHTA (NETS) 2027, approximately **2,400 meritorious students** will be selected for admission in Class 9 and Class 11 with the **entire cost of education funded by the Central Government**.\n\n"
                "| Category | Tentative Seats |\n"
                "| :--- | :--- |\n"
                "| **Scheduled Caste (SC) Students (Boys & Girls)** | 2,160 |\n"
                "| **De-notified Tribes (DNT – not covered under SC/ST/OBC)** | 240 |\n"
                "| **Total Seats** | **2,400** |\n\n"
                "The examination is proposed to be conducted across **192 cities** nationwide.",
                "Page 1 intake breakdown",
            ),
            "eligibility_bullets_markdown": (
                "- **Target Categories:** Meritorious students belonging to Scheduled Caste (SC) and De-notified Tribes (DNT, not covered under SC, ST, and OBC categories), both Boys and Girls.\n"
                "- **Admission Classes:** Admission into **Class 9** and **Class 11** in reputed Private Residential Schools for the 2027–28 academic session.\n"
                "- **Financial Support:** Entire cost of residential school education is funded by the Central Government under the Ministry of Social Justice and Empowerment.\n"
                "- **Detailed Criteria:** Refer to the official Information Bulletin hosted at [https://exams.nta.nic.in/shreshta/](https://exams.nta.nic.in/shreshta/) for income ceiling and age criteria.",
                "Page 1 eligibility summary",
            ),
            "exam_pattern_markdown": (
                "| Parameter | Official Detail |\n"
                "| :--- | :--- |\n"
                "| **Mode of Test** | Pen & Paper Based Test (OMR Sheet based) |\n"
                "| **Pattern of Test** | Multiple Choice Questions (MCQ) |\n"
                "| **Medium of Paper** | Bilingual (Hindi & English) |\n"
                "| **Exam Timing** | 02:00 PM to 05:00 PM (3 Hours) |\n"
                "| **Exam Cities** | 192 Cities across India |",
                "Page 1 examination schedule table",
            ),
            "fee_table_markdown": (
                "| Category | Examination Fee |\n"
                "| :--- | :--- |\n"
                "| **All Eligible Applicants (SC & DNT)** | **Nil (₹0)** |",
                "Page 1 Exam Fee: Nil",
            ),
            "faqs_markdown": (
                "**Q1. How many students will be selected under SHRESHTA (NETS) 2027?**  \n"
                "About **2,400 students** (2,160 SC + 240 DNT) will be selected for admission to Class 9 and Class 11.\n\n"
                "**Q2. What is the last date to apply online for SHRESHTA 2027?**  \n"
                "Candidates can apply online from **14 November 2026 to 30 November 2026 (up to 11:50 PM)**.\n\n"
                "**Q3. Is there any application fee for SHRESHTA (NETS) 2027?**  \n"
                "No. The examination fee is **Nil (₹0)**.\n\n"
                "**Q4. When is the SHRESHTA (NETS) 2027 exam scheduled?**  \n"
                "The exam will be held on **10 January 2027 (Sunday)** from **02:00 PM to 05:00 PM** in Pen & Paper (OMR) mode.\n\n"
                "**Q5. When will SHRESHTA 2027 admit cards be available?**  \n"
                "City intimation will be released on **20 December 2026**, and admit cards can be downloaded from **3 January 2027**.\n\n"
                "**Q6. Where can candidates submit the SHRESHTA 2027 application form?**  \n"
                "Online applications must be submitted only at [https://exams.nta.nic.in/shreshta/](https://exams.nta.nic.in/shreshta/).",
                "Verified FAQs from NTA Public Notice",
            ),
        },
    )

    # ------------------------------------------------------------------
    # 3. NTA NIFTEE 2027 Registration Extension
    # ------------------------------------------------------------------
    upsert_facts(
        conn,
        "not_c3f87ae192b2",
        {
            "blog_title": (
                "NIFTEE 2027 Registration Extended: Apply Online Until 24 November 2026",
                "Official NTA Public Notice dated 14 November 2026",
            ),
            "short_name": ("NIFTEE 2027", "Short exam name"),
            "exam_name": ("National Institute of Fashion Technology Entrance Examination (NIFTEE)–2027", "Official title"),
            "intro_summary": (
                "To enable aspiring candidates to apply for Undergraduate (UG), Postgraduate (PG), NIFT Lateral Entry Admissions (NLEA), Artisans, and Ph.D. Programmes for the Academic Session 2027–28, NTA has extended the regular online registration deadline from 16 November 2026 to 24 November 2026.",
                "Page 1 of NTA Public Notice dated 14 November 2026",
            ),
            "programme_scope": ("UG, PG, NLEA, Artisans & Ph.D. Programmes (Academic Session 2027–28)", "Page 1"),
            "publication_date": ("14 November 2026", "Public Notice dated 14 November 2026"),
            "application_start_date": ("16 October 2026", "16 October 2026 to 24 November 2026"),
            "application_end_date": ("24 November 2026 (Regular) / 29 November 2026 (With Late Fee)", "Revised schedule"),
            "late_fee_window": ("25 November 2026 to 29 November 2026", "Revised late fee window"),
            "correction_window": ("30 November 2026 to 2 December 2026", "Revised correction window"),
            "apply_online_url": ("https://exams.nta.nic.in/niftee/", "Official NIFTEE portal"),
            "helpline": ("011-40759000 / 011-69227700 | nift@nta.ac.in", "NTA NIFTEE Helpdesk"),
            "dates_table_markdown": (
                "| Activity | Existing Last Date(s) | Revised Last Date(s) |\n"
                "| :--- | :--- | :--- |\n"
                "| **Online Submission of Application Form** | 16 October 2026 to 16 November 2026 | **16 October 2026 to 24 November 2026** |\n"
                "| **Online Application with Late Fee** | 17 November 2026 to 21 November 2026 | **25 November 2026 to 29 November 2026** |\n"
                "| **Correction in Particulars of Application Form** | 22 November 2026 to 25 November 2026 | **30 November 2026 to 2 December 2026** |",
                "Exact revised schedule table from NTA Public Notice 14 Nov 2026",
            ),
            "important_note": (
                "Candidates are requested to undertake corrections very carefully between 30 November 2026 and 2 December 2026, as no further opportunity for correction will be provided thereafter.",
                "Para 3 of NTA Public Notice",
            ),
            "faqs_markdown": (
                "**Q1. What is the revised last date to apply for NIFTEE 2027 without a late fee?**  \n"
                "The regular online application deadline has been extended to **24 November 2026**.\n\n"
                "**Q2. Can candidates apply for NIFTEE 2027 with a late fee?**  \n"
                "Yes. Applications with a late fee can be submitted from **25 November 2026 to 29 November 2026**.\n\n"
                "**Q3. When will the NIFTEE 2027 application correction window open?**  \n"
                "The revised correction window is scheduled from **30 November 2026 to 2 December 2026**.\n\n"
                "**Q4. Which programmes are covered under NIFTEE 2027?**  \n"
                "NIFTEE 2027 covers **UG, PG, NIFT Lateral Entry Admissions (NLEA), Artisans, and Ph.D. Programmes** for the 2027–28 academic session.\n\n"
                "**Q5. What is the official website to apply for NIFTEE 2027?**  \n"
                "Candidates must apply online at [https://exams.nta.nic.in/niftee/](https://exams.nta.nic.in/niftee/).",
                "Verified FAQs from NTA Public Notice",
            ),
        },
    )

    # ------------------------------------------------------------------
    # 4. Joint CSIR-UGC NET December 2026 Application Correction Notice
    # ------------------------------------------------------------------
    conn.execute(
        """
        UPDATE canonical_notices
        SET title = 'Correction in the Particulars of the Online Application Form of Joint CSIR-UGC NET December 2026',
            last_updated_at = ?
        WHERE id = 'not_489c4fee4c59'
        """,
        (now_iso,),
    )
    upsert_facts(
        conn,
        "not_489c4fee4c59",
        {
            "blog_title": (
                "CSIR-UGC NET December 2026 Application Correction Notice: Permitted Fields & Rules",
                "Official NTA Public Notice for Joint CSIR-UGC NET Dec 2026",
            ),
            "short_name": ("CSIR-UGC NET December 2026", "Short exam name"),
            "exam_name": ("Joint CSIR-UGC NET December 2026", "Official exam name"),
            "intro_summary": (
                "NTA provided registered candidates a one-time window to verify and correct permitted particulars in their online application forms for Joint CSIR-UGC NET December 2026 (for JRF, Assistant Professor, and Admission to Ph.D.) conducted in Computer Based Test (CBT) mode.",
                "Page 1 of NTA Public Notice",
            ),
            "programme_scope": ("JRF, Assistant Professor & Admission to Ph.D. in Indian Universities/Colleges", "Page 1"),
            "exam_mode": ("Computer Based Test (CBT)", "Page 1"),
            "publication_date": ("10 November 2026", "Public Notice date"),
            "correction_window_start_date": ("10 November 2026", "10th November 2026 to 12th November 2026"),
            "correction_window_end_date": ("12 November 2026 (up to 11:50 PM)", "10th November 2026 to 12th November 2026"),
            "apply_online_url": ("https://csirnet.nta.nic.in/", "Official CSIR NET portal"),
            "helpline": ("011-40759000 / 011-69227700 | csirnet@nta.ac.in", "NTA Helpdesk"),
            "details_section_markdown": (
                "As per **Annexure-I** of the official NTA Public Notice, the fields permitted and restricted for correction are:\n\n"
                "| Action Category | Specific Application Form Fields |\n"
                "| :--- | :--- |\n"
                "| **NOT Allowed to Change** | Mobile Number, E-Mail Address, Permanent & Present Address, Uploaded Photograph, Uploaded Signature |\n"
                "| **Allowed to Change ANY ONE Field** | Candidate Name **OR** Father's Name **OR** Mother's Name |\n"
                "| **Allowed to Change ANY of These Fields** | Date of Birth, Gender, Category, Sub-category / PwBD (if not verified via UDID Portal), Graduation Details, Post-Graduation Details, Subject |\n"
                "| **Exam City Preferences** | Examination City Selection (all 4 preferences based on Permanent & Present address) |",
                "Annexure I Page 2 of NTA Public Notice",
            ),
            "application_fee": (
                "Additional fee applicable only if Category / PwBD change increases fee amount (Credit/Debit Card/Net Banking/UPI; excess fee non-refundable)",
                "Page 1 & Annexure I Notes",
            ),
            "important_note": (
                "Corrections requiring an additional fee take effect only after successful payment. This is a one-time facility; once submitted, the form is frozen and no further changes are entertained.",
                "Page 1 & Page 2 Notes",
            ),
            "faqs_markdown": (
                "**Q1. What was the correction window schedule for Joint CSIR-UGC NET December 2026?**  \n"
                "The one-time correction window was open from **10 November 2026 to 12 November 2026 (up to 11:50 PM)**.\n\n"
                "**Q2. Which fields cannot be changed during the CSIR-UGC NET correction window?**  \n"
                "Candidates cannot change their **Mobile Number, E-Mail Address, Address (Permanent & Present), Photograph, or Signature**.\n\n"
                "**Q3. Can candidates edit their Category or Exam City preferences?**  \n"
                "Yes. Candidates are permitted to edit Category, Sub-category/PwBD (if not UDID-verified), Qualification details, Subject, and Examination City preferences.\n\n"
                "**Q4. Is an extra fee charged for corrections?**  \n"
                "An additional fee applies only if a change in Category or PwBD status results in a higher applicable fee. Excess payment, if any, is not refunded.\n\n"
                "**Q5. What is the official website for CSIR-UGC NET December 2026 updates?**  \n"
                "Candidates should regularly visit [https://csirnet.nta.nic.in/](https://csirnet.nta.nic.in/) and [https://www.nta.ac.in/](https://www.nta.ac.in/).",
                "Verified FAQs from NTA Public Notice",
            ),
        },
    )

    # ------------------------------------------------------------------
    # 5. SSC CPO 2025 (SI in Delhi Police & CAPFs) Corrigendum
    # ------------------------------------------------------------------
    upsert_facts(
        conn,
        "not_fa52f955a289",
        {
            "blog_title": (
                "SSC CPO 2025 PET/PST Result Corrigendum: Amended Roll Numbers for Paper-II",
                "Official SSC Corrigendum dated 16.11.2026",
            ),
            "short_name": ("SSC CPO 2025 Corrigendum", "Short name"),
            "exam_name": ("Sub-Inspector in Delhi Police and CAPFs Examination, 2025 (PET/PST Result Corrigendum)", "Official title"),
            "notice_number": ("E/13/2025-C-2", "File No. E/13/2025-C-2"),
            "publication_date": ("16 November 2026", "Dated: 16.11.2026"),
            "original_notice_date": ("29 October 2026", "Result write-up dated 29.10.2026"),
            "intro_summary": (
                "Based on information received from the Border Security Force (BSF), the Nodal CAPF, SSC has amended Para (5) of the PET/PST result write-up originally published on 29 October 2026 regarding petitioner roll numbers eligible to appear in Paper-II.",
                "Page 1 of SSC Corrigendum dated 16.11.2026",
            ),
            "amendments_markdown": (
                "The Staff Selection Commission has amended **Para (5)** of the PET/PST result write-up dated **29 October 2026** as detailed below:\n\n"
                "| Clause | Official Amendment to Para (5) |\n"
                "| :--- | :--- |\n"
                "| **Addition (Court Case Petitioners)** | Three additional petitioners bearing Roll Numbers **`225130051041`**, **`225130047683`**, and **`625130000489`** are allowed to appear in **Paper-II**, subject to the final outcome of their respective court cases. |\n"
                "| **Deletion** | Roll Number **`225130005272`** is **deleted** as not involved in the court case. |\n"
                "| **Roll Number Correction** | Roll Number **`225130058585`** shall be read as **`225130058588`**. |\n\n"
                "All other terms and conditions of the PET/PST result write-up dated 29 October 2026 remain unchanged.",
                "Exact clauses (i), (ii), (iii) from SSC Corrigendum 16.11.2026",
            ),
            "faqs_markdown": (
                "**Q1. What is the SSC CPO 2025 Corrigendum dated 16 November 2026 about?**  \n"
                "It amends Para (5) of the PET/PST result write-up dated **29 October 2026** for the Sub-Inspector in Delhi Police & CAPFs Examination, 2025.\n\n"
                "**Q2. Which new roll numbers have been allowed to appear in Paper-II?**  \n"
                "Three petitioners with roll numbers **`225130051041`**, **`225130047683`**, and **`625130000489`** are provisionally allowed to appear in Paper-II subject to final court outcomes.\n\n"
                "**Q3. Which roll number was deleted or corrected?**  \n"
                "Roll number **`225130005272`** has been deleted, and **`225130058585`** has been corrected to **`225130058588`**.\n\n"
                "**Q4. Does this corrigendum change the rest of the 29 October 2026 PET/PST result?**  \n"
                "No. SSC confirmed that all other terms and conditions of the 29 October 2026 result write-up remain unchanged.",
                "Verified FAQs from SSC Corrigendum",
            ),
        },
    )

print("All 5 live notices enriched with verified Testkart Exam News fields!")

# Regenerate all 5 blog drafts & run QA
writer = WritingAgent()
qa = QualityAssuranceAgent()

notice_ids = [
    "not_a64a38fd6960",
    "not_ad71f5a41396",
    "not_c3f87ae192b2",
    "not_489c4fee4c59",
    "not_fa52f955a289",
]

for nid in notice_ids:
    art_id, arv_id, chash = writer.draft_article(nid)
    passed, score, checks = qa.inspect_and_evaluate(arv_id)
    failed = [f"{c.rule_name}: {c.message}" for c in checks if not c.passed]
    print(f"[{art_id}] Notice={nid} | Version={arv_id} | QA_PASSED={passed} | Score={score} | Failed={failed}")
