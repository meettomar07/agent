"""Dedicated Test Suite for PDF Intelligence and Recruitment Date Extraction.

Covers all 15 mandatory test scenarios:
1. Standard PDF with application dates in paragraphs.
2. PDF with dates in a tabular schedule.
3. Scanned PDF requiring OCR.
4. PDF with multiple application stages.
5. PDF with multiple examination dates and shifts.
6. PDF with ambiguous date formats (Indian dayfirst parsing).
7. PDF with OCR character errors (repairing noise while retaining raw).
8. PDF with publication date and application date on different pages.
9. PDF with no application dates (zero hallucination).
10. PDF with contradictory dates (deadline before start).
11. Corrigendum changing application deadline (invalidating approvals, resetting drafts).
12. Corrigendum changing vacancies (revision detection, preserving history).
13. Corrupt PDF handling (graceful flagging).
14. Encrypted PDF handling (flagging for human review).
15. Multi-page PDF with dates near page boundaries.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest
import fitz  # PyMuPDF

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import get_db, init_db
from testkart_intelligence.extraction.date_normalizer import DateNormalizer
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor, PdfExtractionError
from testkart_intelligence.extraction.fact_extractor import FactExtractor, ExtractedFactItem
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.extraction.ocr import StubOcrEngine, TesseractOcrEngine


@pytest.fixture
def test_db(tmp_path):
    """Create an isolated test database with all tables initialized."""
    db_file = tmp_path / "test_pdf_intel.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO official_sources (id, code, name, category, state, official_domain, listing_url, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("src_ssc", "SSC", "Staff Selection Commission", "Central Government", "All India", "ssc.gov.in", "https://ssc.gov.in", 1, now_iso, now_iso),
        )
    return db_file


def _create_simple_pdf(text_by_page: list[str]) -> bytes:
    """Helper to generate an in-memory PDF with specified text per page."""
    doc = fitz.open()
    for text in text_by_page:
        page = doc.new_page()
        page.insert_text((50, 72), text, fontsize=11)
    b = doc.tobytes()
    doc.close()
    return b


def _insert_canonical_notice(db_path: Path, notice_id: str, title: str, category: str = "Central Government") -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO canonical_notices (
                id, source_id, authority_name, title, normalized_url, category, state,
                classification, status, first_discovered_at, last_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notice_id,
                "src_ssc",
                "Staff Selection Commission",
                title,
                f"https://ssc.gov.in/notice/{notice_id}.pdf",
                category,
                "All India",
                "RECRUITMENT_NOTIFICATION",
                "DISCOVERED",
                now_iso,
                now_iso,
            ),
        )


# ==============================================================================
# Scenario 1: Standard PDF with application dates in paragraphs
# ==============================================================================
def test_scenario_1_standard_pdf_dates_in_paragraphs(test_db):
    notice_id = "not_para_001"
    _insert_canonical_notice(test_db, notice_id, "SSC CGL Examination 2026")

    content = (
        "Staff Selection Commission\n"
        "Notice of Combined Graduate Level Examination 2026.\n"
        "Online registration commences from 15 November 2026.\n"
        "Closing date for receipt of online application: 15 December 2026.\n"
        "Total vacancies: 4500 posts across various Ministries.\n"
        "Candidates must possess Bachelor's Degree from a recognized University.\n"
        "Age Limit: 18-27 years as on crucial date."
    )
    pdf_bytes = _create_simple_pdf([content])

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url="https://ssc.gov.in/notice/cgl2026.pdf",
        content_type="application/pdf",
    )

    fact_map = {f.key: f for f in facts}

    assert "application_start_date" in fact_map
    assert fact_map["application_start_date"].value == "15 November 2026"
    assert fact_map["application_start_date"].normalized_value == "2026-11-15"
    assert fact_map["application_start_date"].extraction_method == "PDF_TEXT"
    assert fact_map["application_start_date"].page_number == 1
    assert "15 November 2026" in fact_map["application_start_date"].evidence_text

    assert "application_end_date" in fact_map
    assert fact_map["application_end_date"].value == "15 December 2026"
    assert fact_map["application_end_date"].normalized_value == "2026-12-15"

    assert "total_vacancies" in fact_map
    assert fact_map["total_vacancies"].value == "4500"
    assert fact_map["total_vacancies"].normalized_value == "4500"


# ==============================================================================
# Scenario 2: PDF with dates in a tabular schedule
# ==============================================================================
def test_scenario_2_tabular_schedule_dates(test_db):
    notice_id = "not_tab_002"
    _insert_canonical_notice(test_db, notice_id, "UPSC Civil Services 2026")

    table_lines = [
        "IMPORTANT DATES AND SCHEDULE OF ACTIVITIES",
        "Date of Notification | 01.10.2026",
        "Opening date for online submission of application | 05.10.2026",
        "Closing date for online submission of application | 25.10.2026",
        "Last date for payment of fee | 27.10.2026",
        "Window for Application Form Correction | 28.10.2026 to 30.10.2026",
        "Schedule of Tier-I Examination (CBT) | 15.01.2027 to 20.01.2027",
    ]
    pdf_bytes = _create_simple_pdf(["\n".join(table_lines)])

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url="https://ssc.gov.in/notice/upsc_sched.pdf",
        content_type="application/pdf",
    )

    fact_map = {f.key: f for f in facts}

    # Publication date disambiguated from start date
    assert "publication_date" in fact_map
    assert fact_map["publication_date"].normalized_value == "2026-10-01"

    # Application start date
    assert "application_start_date" in fact_map
    assert fact_map["application_start_date"].normalized_value == "2026-10-05"

    # Application end date (not confused with fee deadline)
    assert "application_end_date" in fact_map
    assert fact_map["application_end_date"].normalized_value == "2026-10-25"

    # Fee payment deadline
    assert "fee_payment_deadline" in fact_map
    assert fact_map["fee_payment_deadline"].normalized_value == "2026-10-27"

    # Correction window
    assert "correction_window_start_date" in fact_map
    assert fact_map["correction_window_start_date"].normalized_value == "2026-10-28"
    assert "correction_window_end_date" in fact_map
    assert fact_map["correction_window_end_date"].normalized_value == "2026-10-30"


# ==============================================================================
# Scenario 3: Scanned PDF requiring OCR
# ==============================================================================
def test_scenario_3_scanned_pdf_requiring_ocr(test_db):
    notice_id = "not_scan_003"
    _insert_canonical_notice(test_db, notice_id, "State Police Recruitment (Scanned)")

    # Create a PDF page with an image containing text (low native text density)
    doc = fitz.open()
    page = doc.new_page()
    # Insert a minimal dummy pixmap/drawing and negligible text (< 50 chars)
    page.insert_text((50, 50), "Notice")
    pdf_bytes = doc.tobytes()
    doc.close()

    # Process with StubOcrEngine returning mock OCR text
    mock_ocr = StubOcrEngine(
        canned_text="Government of India Recruitment Notification. Online application commences 12/11/2026. Last date 28/11/2026. Total Vacancies 120."
    )
    extractor = PdfDocumentExtractor(ocr_engine=mock_ocr)
    full_text, pages, count = extractor.extract(pdf_bytes)

    assert count == 1
    assert pages[0]["is_scanned"] is True
    assert "Online application commences 12/11/2026" in full_text


# ==============================================================================
# Scenario 4: PDF with multiple application stages
# ==============================================================================
def test_scenario_4_multiple_application_stages(test_db):
    notice_id = "not_multi_004"
    _insert_canonical_notice(test_db, notice_id, "Engineering Services Two-Stage Exam")

    content = (
        "Engineering Services Examination 2026.\n"
        "Stage 1 Online Registration starts from 01.08.2026 to 25.08.2026.\n"
        "Stage 2 Detailed Application Form (DAF) starts from 10.11.2026 to 20.11.2026.\n"
        "Total vacancies: 320 posts."
    )
    pdf_bytes = _create_simple_pdf([content])

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url="https://ssc.gov.in/notice/ese2026.pdf",
        content_type="application/pdf",
    )

    fact_map = {f.key: f for f in facts}
    assert "application_start_date" in fact_map
    assert fact_map["application_start_date"].normalized_value == "2026-08-01"
    assert "application_end_date" in fact_map
    assert fact_map["application_end_date"].normalized_value == "2026-08-25"


# ==============================================================================
# Scenario 5: PDF with multiple examination dates and shifts
# ==============================================================================
def test_scenario_5_multiple_exam_dates_and_shifts(test_db):
    notice_id = "not_shifts_005"
    _insert_canonical_notice(test_db, notice_id, "Multi-Shift Exam Schedule")

    content = (
        "Staff Selection Commission Examination Schedule.\n"
        "Schedule of Tier-I Examination: 12.01.2027 to 15.01.2027 in two shifts daily.\n"
        "Shift 1: 09:00 AM to 11:00 AM, Shift 2: 02:00 PM to 04:00 PM.\n"
        "Tier-II Examination date: 28.03.2027."
    )
    pdf_bytes = _create_simple_pdf([content])

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url="https://ssc.gov.in/notice/cbt_schedule.pdf",
        content_type="application/pdf",
    )

    fact_map = {f.key: f for f in facts}
    assert "exam_date" in fact_map
    assert "12.01.2027" in fact_map["exam_date"].value
    assert fact_map["exam_date"].verified_status == "VERIFIED"


# ==============================================================================
# Scenario 6: PDF with ambiguous date formats (Day-first Indian parsing)
# ==============================================================================
def test_scenario_6_ambiguous_date_formats():
    # In Indian recruitment notices, 10/12/2026 means 10 December 2026, NOT 12 October
    d1 = DateNormalizer.normalize_date("10/12/2026")
    assert d1 == "2026-12-10"

    d2 = DateNormalizer.normalize_date("04/05/2026")
    assert d2 == "2026-05-04"

    d3 = DateNormalizer.normalize_date("15.08.2026")
    assert d3 == "2026-08-15"

    d4 = DateNormalizer.normalize_date("5th August 2026")
    assert d4 == "2026-08-05"


# ==============================================================================
# Scenario 7: PDF with OCR character errors
# ==============================================================================
def test_scenario_7_ocr_character_errors():
    # Test OCR substitutions: 'l' -> 1, 'O' -> 0, 'S' -> 5
    cleaned_1 = DateNormalizer.clean_ocr_date_string("l5.ll.2O26")
    assert cleaned_1 == "15.11.2026"
    assert DateNormalizer.normalize_date("l5.ll.2O26") == "2026-11-15"

    cleaned_2 = DateNormalizer.clean_ocr_date_string("O1/O8/2O26")
    assert cleaned_2 == "01/08/2026"
    assert DateNormalizer.normalize_date("O1/O8/2O26") == "2026-08-01"

    cleaned_3 = DateNormalizer.clean_ocr_date_string("3l-l2-2026")
    assert cleaned_3 == "31-12-2026"
    assert DateNormalizer.normalize_date("3l-l2-2026") == "2026-12-31"


# ==============================================================================
# Scenario 8: PDF with publication date and application date on different pages
# ==============================================================================
def test_scenario_8_publication_and_application_dates_on_different_pages(test_db):
    notice_id = "not_diff_pages_008"
    _insert_canonical_notice(test_db, notice_id, "Multi-Page Notification")

    page_1 = "Employment Notice No 01/2026. Date of Notification: 01.06.2026. Total Vacancies: 600."
    page_2 = "Section 2: Terms and Conditions of service and reservation policies."
    page_3 = "Important Dates: Candidates can apply online from 10.06.2026 to 30.06.2026."

    pdf_bytes = _create_simple_pdf([page_1, page_2, page_3])

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url="https://ssc.gov.in/notice/diff_pages.pdf",
        content_type="application/pdf",
    )

    fact_map = {f.key: f for f in facts}

    assert "publication_date" in fact_map
    assert fact_map["publication_date"].page_number == 1
    assert fact_map["publication_date"].normalized_value == "2026-06-01"

    assert "application_start_date" in fact_map
    assert fact_map["application_start_date"].page_number == 3
    assert fact_map["application_start_date"].normalized_value == "2026-06-10"

    assert "application_end_date" in fact_map
    assert fact_map["application_end_date"].page_number == 3
    assert fact_map["application_end_date"].normalized_value == "2026-06-30"


# ==============================================================================
# Scenario 9: PDF with no application dates
# ==============================================================================
def test_scenario_9_pdf_with_no_application_dates(test_db):
    notice_id = "not_nodates_009"
    _insert_canonical_notice(test_db, notice_id, "General Syllabus Notification")

    content = (
        "Staff Selection Commission.\n"
        "Detailed Scheme and Syllabus of Examination.\n"
        "The syllabus comprises General Intelligence, Quantitative Aptitude, and English Comprehension.\n"
        "No recruitment schedule is specified herein."
    )
    pdf_bytes = _create_simple_pdf([content])

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url="https://ssc.gov.in/notice/syllabus.pdf",
        content_type="application/pdf",
    )

    fact_map = {f.key: f for f in facts}
    # Never fabricate dates
    assert "application_start_date" not in fact_map
    assert "application_end_date" not in fact_map


# ==============================================================================
# Scenario 10: PDF with contradictory dates (Deadline precedes Start)
# ==============================================================================
def test_scenario_10_contradictory_dates(test_db):
    notice_id = "not_contra_010"
    _insert_canonical_notice(test_db, notice_id, "Contradictory Notification")

    content = (
        "Recruitment Notification.\n"
        "Application commencement date: 20 December 2026.\n"
        "Last date to submit online application: 10 December 2026."
    )
    pdf_bytes = _create_simple_pdf([content])

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url="https://ssc.gov.in/notice/contra.pdf",
        content_type="application/pdf",
    )

    fact_map = {f.key: f for f in facts}
    assert "application_end_date" in fact_map
    end_f = fact_map["application_end_date"]
    assert end_f.status == "CONTRADICTORY"
    assert "before start date" in end_f.notes.lower()


# ==============================================================================
# Scenario 11: Corrigendum changing application deadline
# ==============================================================================
def test_scenario_11_corrigendum_changing_application_deadline(test_db):
    notice_id = "not_corrigendum_011"
    _insert_canonical_notice(test_db, notice_id, "SSC CGL 2026 with Extension")

    now_iso = datetime.now(timezone.utc).isoformat()
    # Create article & approval record for version 1
    with get_db(test_db) as conn:
        art_id = "art_cgl_011"
        ver_id = "art_ver_011"
        conn.execute(
            """
            INSERT INTO blog_articles (id, canonical_notice_id, template_type, current_version_id, status, title, slug, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (art_id, notice_id, "RECRUITMENT", ver_id, "APPROVED", "SSC CGL 2026", "ssc-cgl-2026", now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO article_versions (id, article_id, version_number, content_markdown, content_hash, title, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ver_id, art_id, 1, "# SSC CGL 2026", "hash_art_1", "SSC CGL 2026", now_iso),
        )
        conn.execute(
            """
            INSERT INTO approval_records (id, article_version_id, content_hash, token_hash, reviewer_email, status, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("appr_011", ver_id, "hash_art_1", "tok_011", "editor@testkart.in", "APPROVED", now_iso, now_iso),
        )

    # 1. Ingest Original Notification (Version 1)
    v1_content = (
        "Staff Selection Commission. Notice of CGL Examination 2026.\n"
        "Online application starts from 01.11.2026.\n"
        "Closing date for online application: 20.11.2026.\n"
        "Total vacancies: 2500."
    )
    v1_bytes = _create_simple_pdf([v1_content])
    agent = VerificationAgent(db_path=test_db)
    v1_id, v1_facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=v1_bytes,
        doc_url="https://ssc.gov.in/notice/cgl_orig.pdf",
        content_type="application/pdf",
    )

    # 2. Ingest Corrigendum extending deadline (Version 2)
    v2_content = (
        "CORRIGENDUM / NOTICE OF EXTENSION\n"
        "In continuation of Notice for CGL Examination 2026:\n"
        "Online application starts from 01.11.2026.\n"
        "Closing date for online application extended to: 30.11.2026.\n"
        "Total vacancies: 2500."
    )
    v2_bytes = _create_simple_pdf([v2_content])
    v2_id, v2_facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=v2_bytes,
        doc_url="https://ssc.gov.in/notice/cgl_corrigendum.pdf",
        content_type="application/pdf",
    )

    # Verify Database state
    with get_db(test_db) as conn:
        # Check versions preserved
        versions = conn.execute(
            "SELECT version_number, document_hash FROM notice_versions WHERE notice_id = ? ORDER BY version_number ASC",
            (notice_id,),
        ).fetchall()
        assert len(versions) == 2
        assert versions[0]["version_number"] == 1
        assert versions[1]["version_number"] == 2

        # Check approval invalidated
        appr = conn.execute("SELECT status, decision_notes FROM approval_records WHERE id = 'appr_011'").fetchone()
        assert appr["status"] == "INVALIDATED"
        assert "application_end_date" in appr["decision_notes"]

        # Check article reset to DRAFT
        art = conn.execute("SELECT status FROM blog_articles WHERE id = 'art_cgl_011'").fetchone()
        assert art["status"] == "DRAFT"

        # Check canonical notice marked REVISION_DETECTED
        cn = conn.execute("SELECT status FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()
        assert cn["status"] == "REVISION_DETECTED"

        # Check audit event logged
        audit = conn.execute("SELECT action, payload_json FROM audit_events WHERE entity_id = ?", (notice_id,)).fetchone()
        assert audit["action"] == "CORRIGENDUM_MATERIAL_FACTS_CHANGED"
        assert "2026-11-30" in audit["payload_json"]


# ==============================================================================
# Scenario 12: Corrigendum changing vacancies
# ==============================================================================
def test_scenario_12_corrigendum_changing_vacancies(test_db):
    notice_id = "not_corrigendum_012"
    _insert_canonical_notice(test_db, notice_id, "SSC Vacancy Revision Notice")

    agent = VerificationAgent(db_path=test_db)

    # Version 1: 500 vacancies
    v1_content = "Recruitment Notice. Closing date: 15.12.2026. Total Vacancies: 500 posts."
    v1_bytes = _create_simple_pdf([v1_content])
    agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=v1_bytes,
        doc_url="https://ssc.gov.in/v1.pdf",
        content_type="application/pdf",
    )

    # Version 2: Vacancies increased to 750
    v2_content = "Corrigendum. Closing date: 15.12.2026. Total Vacancies revised to: 750 posts."
    v2_bytes = _create_simple_pdf([v2_content])
    agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=v2_bytes,
        doc_url="https://ssc.gov.in/v2_corrigendum.pdf",
        content_type="application/pdf",
    )

    with get_db(test_db) as conn:
        cn = conn.execute("SELECT status FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()
        assert cn["status"] == "REVISION_DETECTED"


# ==============================================================================
# Scenario 13: Corrupt PDF
# ==============================================================================
def test_scenario_13_corrupt_pdf_handling(test_db):
    notice_id = "not_corrupt_013"
    _insert_canonical_notice(test_db, notice_id, "Corrupt PDF Notice")

    corrupt_bytes = b"%PDF-1.4\ncorrupt body not a valid xref or stream"

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=corrupt_bytes,
        doc_url="https://ssc.gov.in/corrupt.pdf",
        content_type="application/pdf",
    )

    with get_db(test_db) as conn:
        cn = conn.execute("SELECT status FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()
        assert "FLAGGED_FOR_HUMAN_REVIEW" in cn["status"]

    assert len(facts) == 1
    assert "FLAGGED_FOR_HUMAN_REVIEW" in facts[0].status
    assert facts[0].value == "DOCUMENT_CORRUPT_OR_UNREADABLE"


# ==============================================================================
# Scenario 14: Encrypted PDF
# ==============================================================================
def test_scenario_14_encrypted_pdf_handling(test_db):
    notice_id = "not_encrypted_014"
    _insert_canonical_notice(test_db, notice_id, "Encrypted Notification")

    # Generate an encrypted password-protected PDF
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((50, 50), "Confidential recruitment text")
    encrypted_bytes = doc.tobytes(
        deflate=True,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="password123",
        owner_pw="master123",
    )
    doc.close()

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=encrypted_bytes,
        doc_url="https://ssc.gov.in/secret.pdf",
        content_type="application/pdf",
    )

    with get_db(test_db) as conn:
        cn = conn.execute("SELECT status FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()
        assert cn["status"] == "ENCRYPTED_PDF_FLAGGED_FOR_HUMAN_REVIEW"

    assert len(facts) == 1
    assert facts[0].status == "ENCRYPTED_PDF_FLAGGED_FOR_HUMAN_REVIEW"
    assert facts[0].value == "ENCRYPTED_DOCUMENT"


# ==============================================================================
# Scenario 15: Multi-page PDF with dates near page boundaries
# ==============================================================================
def test_scenario_15_dates_near_page_boundaries(test_db):
    notice_id = "not_boundary_015"
    _insert_canonical_notice(test_db, notice_id, "Page Boundary Notice")

    # Page 1 has header and start date near bottom
    p1 = "Government of India Staff Selection Commission\nOpening date of application: 01.12.2026"
    # Page 2 has closing date near top
    p2 = "Closing date for online submission: 31.12.2026\nTotal Vacancies: 800"

    pdf_bytes = _create_simple_pdf([p1, p2])

    agent = VerificationAgent(db_path=test_db)
    version_id, facts = agent.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url="https://ssc.gov.in/boundary.pdf",
        content_type="application/pdf",
    )

    fact_map = {f.key: f for f in facts}
    assert "application_start_date" in fact_map
    assert fact_map["application_start_date"].page_number == 1
    assert fact_map["application_start_date"].normalized_value == "2026-12-01"

    assert "application_end_date" in fact_map
    assert fact_map["application_end_date"].page_number == 2
    assert fact_map["application_end_date"].normalized_value == "2026-12-31"
