"""Automated regression tests for pilot remediation:
1. Category-to-template mapping across all notice categories.
2. Multi-column PDF schedule extraction (actual JEE Main and synthetic layouts).
3. Internal circulars and deputations vs public recruitment safety.
"""

import pytest
from pathlib import Path
import pymupdf
import uuid
from datetime import datetime, timezone

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.editorial.service import EditorialService, StaleVersionConflictError
from testkart_intelligence.publishing.mock_publisher import MockPublisher, MockPublishingError


@pytest.fixture
def remed_test_db(tmp_path: Path):
    """Initializes a temporary database for regression tests."""
    db_file = tmp_path / "test_pilot_remed.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        conn.execute(
            """
            INSERT INTO official_sources (
                id, code, name, category, state, official_domain, listing_url,
                retrieval_method, verification_status, enabled, consecutive_failures,
                created_at, updated_at
            ) VALUES 
            ('src_nta', 'NTA', 'National Testing Agency', 'Teaching/Education', 'Central',
             'nta.ac.in', 'https://nta.ac.in/notices', 'html_scrape', 'VERIFIED', 1, 0,
             '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z'),
            ('src_ssc', 'SSC', 'Staff Selection Commission', 'Central', 'Central',
             'ssc.gov.in', 'https://ssc.gov.in/notices', 'html_scrape', 'VERIFIED', 1, 0,
             '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
    return db_file


# ---------------------------------------------------------------------------
# 1. Template Mapping Tests Across All Notice Categories
# ---------------------------------------------------------------------------
def test_notice_category_to_template_mapping():
    """Verify exact template selection across all notice categories."""
    writer = WritingAgent()

    # Examination schedule / calendar must map to exam_schedule.md.j2, NOT admit_card
    assert writer.select_template(NoticeCategory.EXAM_DATE_ANNOUNCEMENT.value) == "exam_schedule.md.j2"

    # Admit card release must map strictly to admit_card.md.j2
    assert writer.select_template(NoticeCategory.ADMIT_CARD_RELEASE.value) == "admit_card.md.j2"

    # Recruitment must map to recruitment.md.j2
    assert writer.select_template(NoticeCategory.RECRUITMENT_NOTIFICATION.value) == "recruitment.md.j2"

    # Cancellation must map to cancellation.md.j2
    assert writer.select_template(NoticeCategory.CANCELLATION_NOTICE.value) == "cancellation.md.j2"

    # Corrigendum must map to corrigendum.md.j2
    assert writer.select_template(NoticeCategory.CORRIGENDUM.value) == "corrigendum.md.j2"

    # Results & Answer keys
    assert writer.select_template(NoticeCategory.EXAM_RESULT.value) == "result_answer_key.md.j2"
    assert writer.select_template(NoticeCategory.ANSWER_KEY.value) == "result_answer_key.md.j2"

    # Internal Circulars & Deputations
    assert writer.select_template(NoticeCategory.INTERNAL_CIRCULAR.value) == "internal_circular.md.j2"
    assert writer.select_template(NoticeCategory.DEPUTATION_NOTICE.value) == "internal_circular.md.j2"

    # Other announcement fallback
    assert writer.select_template(NoticeCategory.OTHER_ANNOUNCEMENT.value) == "announcement.md.j2"


# ---------------------------------------------------------------------------
# 2. Multi-Column PDF Extraction Tests (Actual JEE Notice & Synthetic)
# ---------------------------------------------------------------------------
def test_multi_column_jee_main_actual_pdf():
    """Verify layout-aware extraction correctly binds dates on actual JEE Main 2027 PDF."""
    pdf_path = Path("data/documents/e5670a67f36b643918aa5012459968a8113581f669923242a87845c9b8d38ae5.pdf")
    if not pdf_path.exists():
        pytest.skip("JEE Main 2027 PDF not found in local workspace")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    extractor = PdfDocumentExtractor()
    full_text, pages, count = extractor.extract(pdf_bytes)

    assert count >= 1
    assert pages[0]["rotation"] == 270 or len(pages[0].get("layout_lines", [])) > 0

    facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name="National Testing Agency",
        notice_title="Joint Entrance Examination (Main) - 2027",
        official_url="https://nta.ac.in/Download/Notice/Notice_20261024220013.pdf",
    )
    fact_dict = {f.key: f for f in facts}

    # Verify application dates are extracted and bound correctly
    assert "application_start_date" in fact_dict
    assert fact_dict["application_start_date"].value == "24th October 2026"
    assert fact_dict["application_start_date"].page_number == 1
    assert "24th October 2026" in fact_dict["application_start_date"].evidence_text

    assert "application_end_date" in fact_dict
    assert fact_dict["application_end_date"].value == "22nd November 2026"
    assert fact_dict["application_end_date"].page_number == 1

    # Verify admit card date is extracted correctly
    assert "admit_card_date" in fact_dict
    assert fact_dict["admit_card_date"].value == "13th January 2027"

    # Verify exam date is bound to the actual examination row, NOT late submission window
    assert "exam_date" in fact_dict
    assert fact_dict["exam_date"].value == "20,21,22,23,24 and 28 January 2027"
    assert fact_dict["exam_date"].value != "23rd November 2026 to 26th November 2026"


def test_multi_column_synthetic_schedule_table():
    """Verify layout-aware row clustering on synthetic 2-column table PDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)

    # Insert two separate columns at same vertical row
    # Left column: event labels
    page.insert_text((50, 100), "Online Submission of Application Form", fontsize=11)
    page.insert_text((50, 150), "Downloading of Admit Cards from Website", fontsize=11)
    page.insert_text((50, 200), "Date of Examination", fontsize=11)

    # Right column: dates
    page.insert_text((350, 100), "01.12.2026 to 31.12.2026", fontsize=11)
    page.insert_text((350, 150), "15.01.2027", fontsize=11)
    page.insert_text((350, 200), "25.01.2027 to 30.01.2027", fontsize=11)

    pdf_bytes = doc.tobytes()
    doc.close()

    extractor = PdfDocumentExtractor()
    full_text, pages, count = extractor.extract(pdf_bytes)

    facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name="Staff Selection Commission",
        notice_title="Combined Graduate Level Examination 2026",
        official_url="https://ssc.gov.in/cgl.pdf",
    )
    fact_dict = {f.key: f for f in facts}

    assert "application_start_date" in fact_dict
    assert fact_dict["application_start_date"].value == "01.12.2026"
    assert fact_dict["application_end_date"].value == "31.12.2026"

    assert "admit_card_date" in fact_dict
    assert fact_dict["admit_card_date"].value == "15.01.2027"

    assert "exam_date" in fact_dict
    assert fact_dict["exam_date"].value == "25.01.2027 to 30.01.2027"


# ---------------------------------------------------------------------------
# 3. Internal Circulars vs Public Recruitment Safety Tests
# ---------------------------------------------------------------------------
def test_internal_circular_classification_precedence():
    """Verify LDCE and Deputation notices are prioritized over public recruitment."""
    # SSC LDCE notice with vacancies
    cat1 = NoticeClassifier.classify(
        title="Tentative Vacancy of Grade 'C' Stenographers Limited Departmental Competitive Examination, 2025",
        facts={"total_vacancies": "314"},
        authority_name="Staff Selection Commission",
    )
    assert cat1 == NoticeCategory.INTERNAL_CIRCULAR

    # NTA Deputation notice
    cat2 = NoticeClassifier.classify(
        title="Extension of last date for inviting application for various posts in National Testing agency (NTA) on deputation basis-Reg",
        authority_name="National Testing Agency",
    )
    assert cat2 == NoticeCategory.DEPUTATION_NOTICE

    # Normal public recruitment notice
    cat3 = NoticeClassifier.classify(
        title="Combined Graduate Level Examination, 2026 (Direct Recruitment)",
        facts={"total_vacancies": "10000", "application_start_date": "01.12.2026", "application_end_date": "31.12.2026"},
    )
    assert cat3 == NoticeCategory.RECRUITMENT_NOTIFICATION


def test_internal_circular_drafting_and_qa_safety(remed_test_db: Path):
    """Verify internal circular is rendered with restricted template and passes QA without public claims."""
    now_iso = datetime.now(timezone.utc).isoformat()
    notice_id = "cn_ldce_test"
    art_id = "art_ldce_test"

    with get_db(remed_test_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
            ) VALUES (
                ?, 'src_ssc', 'Staff Selection Commission', 'LDCE-2025',
                'Grade C Stenographers Limited Departmental Competitive Examination 2025',
                'https://ssc.gov.in/ldce.pdf', 'Central', 'Central', 'INTERNAL_CIRCULAR', 'EXTRACTED',
                '2026-10-24', 'CURRENT', 'NONE', ?, ?
            )
            """,
            (notice_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES ('ver_ldce_1', ?, 1, 'https://ssc.gov.in/ldce.pdf', 'hash_ldce', 'PDF', 'mock.pdf',
                      'Limited Departmental Examination 2025 Vacancies: 314', 1, ?)
            """,
            (notice_id, now_iso),
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, evidence_text, page_number, confidence, verified_status, created_at
            ) VALUES 
            ('f_auth', 'ver_ldce_1', 'recruiting_authority', 'Staff Selection Commission', 'Staff Selection Commission', 1, 1.0, 'VERIFIED', ?),
            ('f_url', 'ver_ldce_1', 'official_source_url', 'https://ssc.gov.in/ldce.pdf', 'https://ssc.gov.in/ldce.pdf', 1, 1.0, 'VERIFIED', ?),
            ('f_vac', 'ver_ldce_1', 'total_vacancies', '314', 'Vacancies: 314', 1, 0.95, 'VERIFIED', ?)
            """,
            (now_iso, now_iso, now_iso),
        )

    writer = WritingAgent(db_path=remed_test_db)
    qa = QualityAssuranceAgent(db_path=remed_test_db)

    # Draft article
    res_art_id, arv_id, h = writer.draft_article(notice_id)
    assert arv_id.startswith("arv_")

    # Run QA
    passed, score, checks = qa.inspect_and_evaluate(arv_id)
    assert passed is True
    assert score == 100.0

    # Ensure rule_internal_circular_safety passed
    safety_check = next((c for c in checks if c.rule_name == "rule_internal_circular_safety"), None)
    assert safety_check is not None
    assert safety_check.passed is True

    # Ensure article content contains internal restriction notice
    with get_db(remed_test_db) as conn:
        av = conn.execute("SELECT content_markdown FROM article_versions WHERE id = ?", (arv_id,)).fetchone()
        md = av["content_markdown"]
        assert "NOT open to direct public" in md
        assert "proper official channel" in md
        assert "direct recruitment" not in md.lower()


def test_controlled_approval_invalidation_workflow(remed_test_db: Path):
    """Verify that an approved article version cannot authorize a revised version, and audit trails record exact hashes."""
    now_iso = datetime.now(timezone.utc).isoformat()
    service = EditorialService(db_path=remed_test_db)
    writer = WritingAgent(db_path=remed_test_db)
    qa = QualityAssuranceAgent(db_path=remed_test_db)
    publisher = MockPublisher(db_path=remed_test_db)

    # 1. Setup canonical notice
    notice_id = "not_rev_test"
    with get_db(remed_test_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_ssc', 'Staff Selection Commission', '01/2026',
                      'Assistant Engineer Examination 2026', 'https://ssc.gov.in/ae-2026.pdf',
                      'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
                      '2026-10-24', ?, ?)
            """,
            (notice_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES ('nv_1', ?, 1, 'https://ssc.gov.in/ae-2026.pdf',
                      'hash_nv1', 'PDF', 'mock.pdf', 'Assistant Engineer Examination 2026', 1, ?)
            """,
            (notice_id, now_iso),
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, evidence_text, page_number, confidence, verified_status, created_at
            ) VALUES
            ('f1', 'nv_1', 'recruiting_authority', 'Staff Selection Commission', 'Staff Selection Commission', 1, 1.0, 'VERIFIED', ?),
            ('f2', 'nv_1', 'official_source_url', 'https://ssc.gov.in/ae-2026.pdf', 'https://ssc.gov.in', 1, 1.0, 'VERIFIED', ?),
            ('f3', 'nv_1', 'application_start_date', '01.11.2026', '01.11.2026', 1, 0.95, 'VERIFIED', ?),
            ('f4', 'nv_1', 'application_end_date', '30.11.2026', '30.11.2026', 1, 0.95, 'VERIFIED', ?),
            ('f5', 'nv_1', 'total_vacancies', '150', '150 posts', 1, 0.95, 'VERIFIED', ?)
            """,
            (now_iso, now_iso, now_iso, now_iso, now_iso),
        )

    # 2. Draft Version 1
    art_id, arv1_id, hash_v1 = writer.draft_article(notice_id)
    passed, score, _ = qa.inspect_and_evaluate(arv1_id)
    assert passed is True

    # 3. Approve Version 1 explicitly in local review workflow
    dec_result = service.submit_decision(
        article_id=art_id,
        expected_version_id=arv1_id,
        expected_content_hash=hash_v1,
        decision="APPROVE",
        editor_email="meettomar07@gmail.com",
        notes="All dates and facts verified against official AE-2026 PDF.",
    )
    assert dec_result["decision"] == "APPROVED"

    with get_db(remed_test_db) as conn:
        art_row = conn.execute("SELECT status, current_version_id FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert art_row["status"] == "APPROVED"
        assert art_row["current_version_id"] == arv1_id

    # 4. Simulate official corrigendum / revision
    with get_db(remed_test_db) as conn:
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES ('nv_2', ?, 2, 'https://ssc.gov.in/ae-2026-corrigendum.pdf',
                      'hash_nv2', 'PDF', 'mock2.pdf', 'Corrigendum: Application deadline extended to 15.12.2026', 1, ?)
            """,
            (notice_id, now_iso),
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, evidence_text, page_number, confidence, verified_status, created_at
            ) VALUES
            ('f1_v2', 'nv_2', 'recruiting_authority', 'Staff Selection Commission', 'Staff Selection Commission', 1, 1.0, 'VERIFIED', ?),
            ('f2_v2', 'nv_2', 'official_source_url', 'https://ssc.gov.in/ae-2026-corrigendum.pdf', 'https://ssc.gov.in', 1, 1.0, 'VERIFIED', ?),
            ('f3_v2', 'nv_2', 'application_start_date', '01.11.2026', '01.11.2026', 1, 0.95, 'VERIFIED', ?),
            ('f4_v2', 'nv_2', 'application_end_date', '15.12.2026', '15.12.2026 (Extended)', 1, 0.95, 'VERIFIED', ?),
            ('f5_v2', 'nv_2', 'total_vacancies', '180', '180 posts', 1, 0.95, 'VERIFIED', ?)
            """,
            (now_iso, now_iso, now_iso, now_iso, now_iso),
        )

    # Regenerate article draft for the revised notice version
    art_id2, arv2_id, hash_v2 = writer.draft_article(notice_id, notice_version_id="nv_2")
    assert art_id2 == art_id
    assert arv2_id != arv1_id
    assert hash_v2 != hash_v1

    # 5. Confirm old approval cannot authorize new version & status reset to DRAFT
    with get_db(remed_test_db) as conn:
        art_row_after = conn.execute("SELECT status, current_version_id FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert art_row_after["status"] == "DRAFT"
        assert art_row_after["current_version_id"] == arv2_id

        # Version 2 has 0 approval records
        v2_approvals = conn.execute("SELECT * FROM approval_records WHERE article_version_id = ?", (arv2_id,)).fetchall()
        assert len(v2_approvals) == 0

        # Old approval record is bound strictly to arv1_id
        v1_approvals = conn.execute("SELECT id, article_version_id, content_hash FROM approval_records WHERE article_version_id = ?", (arv1_id,)).fetchall()
        assert len(v1_approvals) == 1
        v1_appr_id = v1_approvals[0]["id"]

    # 6. Verify MockPublisher strictly BLOCKS publication of Version 2 with old approval
    with pytest.raises(MockPublishingError, match="Content hash mismatch"):
        publisher.publish(
            article_version_id=arv2_id,
            content_hash=hash_v2,
            approval_record_id=v1_appr_id,
        )

    # 7. Verify stale decision submission on old version is rejected
    with pytest.raises(StaleVersionConflictError):
        service.submit_decision(
            article_id=art_id,
            expected_version_id=arv1_id,
            expected_content_hash=hash_v1,
            decision="APPROVE",
            editor_email="meettomar07@gmail.com",
        )

    # 8. Verify audit trail records exact version hash and decision
    with get_db(remed_test_db) as conn:
        audit_events = conn.execute("SELECT action, payload_json FROM audit_events WHERE entity_id = ?", (v1_appr_id,)).fetchall()
        assert len(audit_events) >= 1
        assert "EDITORIAL_APPROVED" in [ae["action"] for ae in audit_events]
        assert hash_v1 in audit_events[0]["payload_json"]
