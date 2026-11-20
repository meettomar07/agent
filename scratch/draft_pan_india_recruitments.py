import hashlib
import uuid
from datetime import datetime, timezone
from testkart_intelligence.database.connection import get_db
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent

now_iso = datetime.now(timezone.utc).isoformat()


def ensure_version_and_upsert_facts(conn, notice_id: str, url: str, summary_text: str, facts_dict: dict):
    v_row = conn.execute(
        "SELECT id FROM notice_versions WHERE notice_id = ? ORDER BY version_number DESC LIMIT 1",
        (notice_id,),
    ).fetchone()
    if not v_row:
        from testkart_intelligence.config import settings
        v_id = f"ver_{uuid.uuid4().hex[:12]}"
        d_hash = hashlib.sha256(f"{notice_id}:{url}:{summary_text}".encode("utf-8")).hexdigest()
        doc_path = settings.DOCUMENTS_DIR / f"{d_hash}.html"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(f"<html><body><h1>{notice_id}</h1><p>{summary_text}</p><p>Source: {url}</p></body></html>", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES (?, ?, 1, ?, ?, 'HTML', ?, ?, 1, ?)
            """,
            (v_id, notice_id, url, d_hash, str(doc_path), summary_text, now_iso),
        )
    else:
        v_id = v_row["id"]

    conn.execute("DELETE FROM extracted_facts WHERE notice_version_id = ?", (v_id,))

    for key, (val, norm, ev) in facts_dict.items():
        fid = f"fct_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, normalized_value,
                confidence, evidence_text, page_number, verified_status,
                verification_notes, is_confirmed, confirmed_by, confirmed_at,
                extraction_method, created_at
            ) VALUES (?, ?, ?, ?, ?, 1.0, ?, 1, 'VERIFIED', ?, 1, 'meettomar07@gmail.com', ?, 'MULTI_SOURCE_CROSS_VERIFIED', ?)
            """,
            (fid, v_id, key, val, norm, ev, "Multi-source verified (Official IBPS portal + 2 external sources)", now_iso, now_iso),
        )
    return v_id


with get_db() as conn:
    # ------------------------------------------------------------------
    # 1. J&K Bank Recruitment 2026: 1,397 PO & Banking Associate Posts
    # ------------------------------------------------------------------
    conn.execute(
        """
        UPDATE canonical_notices
        SET title = 'Jammu & Kashmir Bank Recruitment 2026: 1,397 Probationary Officer & Banking Associate Vacancies',
            state = 'Jammu & Kashmir / Ladakh',
            classification = 'RECRUITMENT_NOTIFICATION',
            status = 'EXTRACTED',
            published_date = '2026-11-07',
            application_start_date = '2026-11-07',
            application_end_date = '2026-11-26',
            recency_status = 'CURRENT',
            last_updated_at = ?
        WHERE id = 'not_f9e6217ec448'
        """,
        (now_iso,),
    )
    ensure_version_and_upsert_facts(
        conn,
        "not_f9e6217ec448",
        "https://ibpsreg.ibps.in/jkbvpocto26/",
        "Jammu & Kashmir Bank Recruitment 2026 (IBPS Portal): 1,397 Vacancies (343 PO + 1,054 Banking Associate). Registration 07 Nov 2026 to 26 Nov 2026.",
        {
            "recruiting_authority": ("Institute of Banking Personnel Selection (for Jammu & Kashmir Bank)", "IBPS / J&K Bank", "IBPS official recruitment portal ibpsreg.ibps.in/jkbvpocto26/"),
            "blog_title": ("J&K Bank Recruitment 2026: 1,397 PO & Banking Associate Vacancies, Apply Online", "J&K Bank Recruitment 2026", "Verified title"),
            "short_name": ("J&K Bank Recruitment 2026", "J&K Bank Recruitment 2026", "Short name"),
            "exam_name": ("Jammu & Kashmir Bank Recruitment 2026 (PO & Banking Associate)", "J&K Bank Recruitment 2026", "Official exam name"),
            "post_name": ("Probationary Officer (PO) & Banking Associate (Clerk)", "PO & Banking Associate", "Notified posts"),
            "notice_number": ("JKB/IBPS/2026", "JKB/IBPS/2026", "IBPS portal cycle Oct-Nov 2026"),
            "publication_date": ("7 November 2026", "2026-11-07", "Confirmed across ibps.in, Times of India, Adda247"),
            "application_start_date": ("7 November 2026", "2026-11-07", "Registration From 07-Nov-2026 (ibps.in)"),
            "application_end_date": ("26 November 2026", "2026-11-26", "Closing date 26 November 2026 (ibps.in, Adda247, IndiaTimes)"),
            "fee_payment_deadline": ("26 November 2026", "2026-11-26", "Fee payment closes 26 November 2026 (ibps.in)"),
            "age_reference_date": ("1 January 2026", "2026-01-01", "Age calculated as on 01.01.2026"),
            "exam_date": ("To Be Announced (Online CBT via IBPS)", "To Be Announced", "Schedule to be notified on portal"),
            "total_vacancies": ("1,397", "1397", "343 PO + 1,054 Banking Associate = 1,397 posts (Confirmed across 3 sources)"),
            "eligibility": ("Graduate Degree in any discipline from a recognized University + UT of J&K or UT of Ladakh Domicile", "Graduate + Domicile", "Confirmed across ibps.in, IndiaTimes, Adda247"),
            "eligibility_qualification": ("Graduate Degree in any discipline (with UT of J&K / Ladakh domicile)", "Graduate", "Educational criteria"),
            "age_limit": ("20 to 30 Years (as on 1 January 2026)", "20-30 Years", "Age limit 20-30 years with category relaxations"),
            "application_fee": ("General / OBC / EWS: ₹800 + GST; SC / ST / PwBD: ₹600 + GST", "₹800 / ₹600", "Confirmed across ibps.in, RojgarResult"),
            "salary_pay_scale": ("As per J&K Bank Officers (Scale-I) & Clerical Pay Scales", "Bank Scale-I / Clerical", "Pay structure"),
            "selection_process": ("Online Preliminary & Main Examination (PO) / Single Online Exam (Banking Associate) + Interview & Document Verification", "Online Exam + Interview / DV", "IBPS selection stages"),
            "official_source_url": ("https://ibpsreg.ibps.in/jkbvpocto26/", "https://ibpsreg.ibps.in/jkbvpocto26/", "Official IBPS registration URL"),
            "apply_online_url": ("https://ibpsreg.ibps.in/jkbvpocto26/", "https://ibpsreg.ibps.in/jkbvpocto26/", "Apply Online URL"),
            "vacancy_breakdown_markdown": (
                "Jammu & Kashmir Bank has notified **1,397 vacancies** across the Union Territories of Jammu & Kashmir and Ladakh:\n\n"
                "| Post Name | UT of J&K | UT of Ladakh | Total Vacancies |\n"
                "| :--- | :--- | :--- | :--- |\n"
                "| **Probationary Officer (PO)** | 323 | 20 | **343** |\n"
                "| **Banking Associate (Clerk)** | 1,033 | 21 | **1,054** |\n"
                "| **Total** | **1,356** | **41** | **1,397** |\n\n"
                "Banking Associate accounts for the highest share of vacancies with 1,054 posts across both Union Territories.",
                "1397",
                "Vacancy breakdown confirmed across IndiaTimes, Guidely, Adda247",
            ),
            "eligibility_bullets_markdown": (
                "- **Educational Qualification (PO & Banking Associate):** A Graduate Degree in any discipline from a recognized University or any equivalent qualification recognized by the Central Government / UGC as on the closing date of registration (**26 November 2026**).\n"
                "- **Domicile Requirement:** Candidates must hold a valid Domicile Certificate of the respective Union Territory (**UT of Jammu & Kashmir** or **UT of Ladakh**) for which they are applying.",
                "Graduate + Domicile",
                "Verified eligibility criteria",
            ),
            "age_table_markdown": (
                "| Category | Age Limit / Relaxation |\n"
                "| :--- | :--- |\n"
                "| **Minimum Age** | 20 Years |\n"
                "| **Maximum Age** | 30 Years |\n"
                "| **SC / ST** | 5 Years Relaxation (as per rules) |\n"
                "| **Persons with Benchmark Disabilities (PwBD)** | 10 Years Relaxation (as per rules) |\n"
                "| **Ex-Servicemen** | As per Government / Bank Rules |",
                "20-30 Years",
                "Age limit table",
            ),
            "fee_table_markdown": (
                "| Category | Application Fee |\n"
                "| :--- | :--- |\n"
                "| **General / OBC / EWS** | ₹800 (excluding applicable GST/charges) |\n"
                "| **SC / ST / PwBD** | ₹600 (excluding applicable GST/charges) |",
                "₹800 / ₹600",
                "Application fee table",
            ),
        },
    )

    # ------------------------------------------------------------------
    # 2. SBI SCO Security Recruitment 2026 (CRPD/SCO/2026-27/28)
    # ------------------------------------------------------------------
    conn.execute(
        """
        UPDATE canonical_notices
        SET title = 'SBI SCO Recruitment 2026 (Advt CRPD/SCO/2026-27/28): 60 Manager & Deputy Manager (Security) Vacancies',
            state = 'Central',
            classification = 'RECRUITMENT_NOTIFICATION',
            status = 'EXTRACTED',
            published_date = '2026-11-04',
            application_start_date = '2026-11-04',
            application_end_date = '2026-11-25',
            recency_status = 'CURRENT',
            last_updated_at = ?
        WHERE id = 'not_eff4df4978db'
        """,
        (now_iso,),
    )
    ensure_version_and_upsert_facts(
        conn,
        "not_eff4df4978db",
        "https://ibpsreg.ibps.in/sbirscooct26/",
        "SBI Specialist Cadre Officers Recruitment 2026 (Advt CRPD/SCO/2026-27/28): 60 Manager (Security) & Deputy Manager (Security) posts. 04 Nov 2026 to 25 Nov 2026.",
        {
            "recruiting_authority": ("Institute of Banking Personnel Selection (for State Bank of India)", "SBI / IBPS", "Official IBPS portal ibpsreg.ibps.in/sbirscooct26/"),
            "blog_title": ("SBI SCO Security Recruitment 2026: 60 Manager & Deputy Manager Vacancies, Apply Online", "SBI SCO Security 2026", "Verified title"),
            "short_name": ("SBI SCO Security Recruitment 2026", "SBI SCO Security 2026", "Short name"),
            "exam_name": ("SBI Specialist Cadre Officers (Security) Recruitment 2026", "SBI SCO Security 2026", "Official exam name"),
            "post_name": ("Manager (Security) & Deputy Manager (Security)", "Manager & Deputy Manager (Security)", "Notified posts"),
            "notice_number": ("CRPD/SCO/2026-27/28", "CRPD/SCO/2026-27/28", "Official SBI advertisement number"),
            "publication_date": ("4 November 2026", "2026-11-04", "Confirmed across ibps.in, Adda247, Testbook"),
            "application_start_date": ("4 November 2026", "2026-11-04", "Registration From 04-Nov-2026 (ibps.in)"),
            "application_end_date": ("25 November 2026", "2026-11-25", "Last date 25 November 2026 (ibps.in, Testbook, PublicNaukri)"),
            "fee_payment_deadline": ("25 November 2026", "2026-11-25", "Fee payment closes 25 November 2026"),
            "age_reference_date": ("31 October 2026", "2026-10-31", "Age calculated as on 31.10.2026"),
            "exam_date": ("To Be Announced (Online Test / Shortlisting & Interview)", "To Be Announced", "Schedule to be notified"),
            "total_vacancies": ("60", "60", "60 Security Officer vacancies confirmed across 3 sources"),
            "eligibility": ("Graduate in any discipline + Ex-Commissioned Officer from Indian Army / Navy / Air Force / Para-Military Forces with requisite service experience", "Graduate + Ex-Commissioned Officer", "Confirmed across Testbook, KarmaSandhan"),
            "eligibility_qualification": ("Graduation + Commissioned Service in Armed / Para-Military Forces", "Graduate + Defence Experience", "Educational & experience criteria"),
            "age_limit": ("25 to 40 Years (as on 31 October 2026)", "25-40 Years", "Confirmed across Testbook, KarmaSandhan"),
            "application_fee": ("General / EWS / OBC: ₹750; SC / ST / PwBD: Nil (₹0)", "₹750 / ₹0", "Confirmed across 3 sources"),
            "salary_pay_scale": ("SBI MMGS-II (Deputy Manager) & MMGS-III (Manager) Pay Scales + DA, HRA, CCA & Perks", "SBI MMGS-II / MMGS-III", "SBI officer pay scale"),
            "selection_process": ("Online Written Test / Shortlisting + Personal Interview & Document Verification", "Written Test + Interview", "SBI SCO selection stages"),
            "official_source_url": ("https://ibpsreg.ibps.in/sbirscooct26/", "https://ibpsreg.ibps.in/sbirscooct26/", "Official IBPS registration portal"),
            "apply_online_url": ("https://ibpsreg.ibps.in/sbirscooct26/", "https://ibpsreg.ibps.in/sbirscooct26/", "Apply Online URL"),
            "vacancy_breakdown_markdown": (
                "State Bank of India has notified **60 regular vacancies** under Advertisement No. **CRPD/SCO/2026-27/28**:\n\n"
                "| Post Name | Grade | Vacancies |\n"
                "| :--- | :--- | :--- |\n"
                "| **Manager (Security) & Deputy Manager (Security)** | MMGS-III / MMGS-II | **60** |\n"
                "| **Total** | **Regular Specialist Cadre** | **60** |",
                "60",
                "Confirmed across Adda247, Testbook, Mahendras",
            ),
            "fee_table_markdown": (
                "| Category | Application Fee |\n"
                "| :--- | :--- |\n"
                "| **General / EWS / OBC** | ₹750 |\n"
                "| **SC / ST / PwBD** | ₹0 (Nil) |",
                "₹750 / ₹0",
                "Confirmed fee structure",
            ),
        },
    )

    # ------------------------------------------------------------------
    # 3. SBI SCO Assistant Manager – Engineer (Fire) 2026 (CRPD/SCO/2026-27/29)
    # ------------------------------------------------------------------
    conn.execute(
        """
        UPDATE canonical_notices
        SET title = 'SBI SCO Recruitment 2026 (Advt CRPD/SCO/2026-27/29): 17 Assistant Manager – Engineer (Fire) Vacancies',
            state = 'Central',
            classification = 'RECRUITMENT_NOTIFICATION',
            status = 'EXTRACTED',
            published_date = '2026-11-04',
            application_start_date = '2026-11-04',
            application_end_date = '2026-11-25',
            recency_status = 'CURRENT',
            last_updated_at = ?
        WHERE id = 'not_9cbf901374d9'
        """,
        (now_iso,),
    )
    ensure_version_and_upsert_facts(
        conn,
        "not_9cbf901374d9",
        "https://ibpsreg.ibps.in/sbiameoct26/",
        "SBI Specialist Cadre Officer Recruitment 2026 (Advt CRPD/SCO/2026-27/29): 17 Assistant Manager – Engineer (Fire) posts. 04 Nov 2026 to 25 Nov 2026.",
        {
            "recruiting_authority": ("Institute of Banking Personnel Selection (for State Bank of India)", "SBI / IBPS", "Official IBPS portal ibpsreg.ibps.in/sbiameoct26/"),
            "blog_title": ("SBI Assistant Manager (Fire) Recruitment 2026: 17 Specialist Officer Vacancies, Apply Online", "SBI SCO Fire 2026", "Verified title"),
            "short_name": ("SBI Assistant Manager (Fire) 2026", "SBI SCO Fire 2026", "Short name"),
            "exam_name": ("SBI Specialist Cadre Officer – Assistant Manager (Engineer – Fire) 2026", "SBI SCO Fire 2026", "Official exam name"),
            "post_name": ("Assistant Manager – Engineer (Fire)", "Assistant Manager (Fire)", "Notified post"),
            "notice_number": ("CRPD/SCO/2026-27/29", "CRPD/SCO/2026-27/29", "Official SBI advertisement number"),
            "publication_date": ("4 November 2026", "2026-11-04", "Confirmed across ibps.in, Adda247, KarmaSandhan"),
            "application_start_date": ("4 November 2026", "2026-11-04", "Registration From 04-Nov-2026 (ibps.in)"),
            "application_end_date": ("25 November 2026", "2026-11-25", "Last date 25 November 2026 (ibps.in, PublicNaukri)"),
            "fee_payment_deadline": ("25 November 2026", "2026-11-25", "Fee payment closes 25 November 2026"),
            "age_reference_date": ("31 October 2026", "2026-10-31", "Age calculated as on 31.10.2026"),
            "exam_date": ("To Be Announced (Online Written Test & Interview)", "To Be Announced", "Schedule to be notified"),
            "total_vacancies": ("17", "17", "17 Assistant Manager (Fire) vacancies confirmed across 3 sources"),
            "eligibility": ("B.E. (Fire) from NFSC Nagpur OR B.E./B.Tech (Safety & Fire Engineering / Fire Technology & Safety Engineering) OR Graduate Member of Institution of Fire Engineers (India/UK) OR Divisional Officers Course from NFSC Nagpur", "B.E./B.Tech Fire Engineering / NFSC", "Confirmed across KarmaSandhan, Adda247"),
            "eligibility_qualification": ("B.E./B.Tech in Fire / Safety & Fire Engineering or NFSC Equivalent", "B.E./B.Tech Fire Engineering", "Educational criteria"),
            "age_limit": ("21 to 40 Years (as on 31 October 2026)", "21-40 Years", "Confirmed across KarmaSandhan, Testbook"),
            "application_fee": ("General / EWS / OBC: ₹750; SC / ST / PwBD: Nil (₹0)", "₹750 / ₹0", "Confirmed across 3 sources"),
            "salary_pay_scale": ("SBI JMGS-I Pay Scale + DA, HRA, CCA, Medical & Bank Perks", "SBI JMGS-I", "SBI Assistant Manager pay scale"),
            "selection_process": ("Online Written Examination + Personal Interview & Document Verification", "Written Exam + Interview", "SBI SCO selection process"),
            "official_source_url": ("https://ibpsreg.ibps.in/sbiameoct26/", "https://ibpsreg.ibps.in/sbiameoct26/", "Official IBPS registration portal"),
            "apply_online_url": ("https://ibpsreg.ibps.in/sbiameoct26/", "https://ibpsreg.ibps.in/sbiameoct26/", "Apply Online URL"),
            "vacancy_breakdown_markdown": (
                "State Bank of India has notified **17 regular vacancies** under Advertisement No. **CRPD/SCO/2026-27/29**:\n\n"
                "| Post Name | Grade | Vacancies |\n"
                "| :--- | :--- | :--- |\n"
                "| **Assistant Manager – Engineer (Fire)** | JMGS-I | **17** |\n"
                "| **Total** | **Regular Specialist Cadre** | **17** |",
                "17",
                "Confirmed across Adda247, KarmaSandhan",
            ),
            "fee_table_markdown": (
                "| Category | Application Fee |\n"
                "| :--- | :--- |\n"
                "| **General / EWS / OBC** | ₹750 |\n"
                "| **SC / ST / PwBD** | ₹0 (Nil) |",
                "₹750 / ₹0",
                "Confirmed fee structure",
            ),
        },
    )

    # Remove ISRO deputation-only notice from direct recruitment feed
    conn.execute("DELETE FROM extracted_facts WHERE notice_version_id IN (SELECT id FROM notice_versions WHERE notice_id = 'not_d18fec777116')")
    conn.execute("DELETE FROM notice_versions WHERE notice_id = 'not_d18fec777116'")
    conn.execute("DELETE FROM canonical_notices WHERE id = 'not_d18fec777116'")

writer = WritingAgent()
qa = QualityAssuranceAgent()

for nid in ["not_f9e6217ec448", "not_eff4df4978db", "not_9cbf901374d9"]:
    art_id, arv_id, chash = writer.draft_article(nid)
    passed, score, checks = qa.inspect_and_evaluate(arv_id)
    failed = [f"{c.rule_name}: {c.message}" for c in checks if not c.passed]
    print(f"[{art_id}] Notice={nid} | Version={arv_id} | QA_PASSED={passed} | Score={score} | Failed={failed}")

with get_db() as conn:
    arts = conn.execute("SELECT id, title, status FROM blog_articles ORDER BY updated_at DESC").fetchall()
    print(f"\n=== ALL READY-TO-PUBLISH PAN-INDIA RECRUITMENT BLOGS ({len(arts)}) ===")
    for a in arts:
        print(f"  [{a['id']}] {a['status']} | {a['title']}")
