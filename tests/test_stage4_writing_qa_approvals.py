"""Unit tests for Stage 4: Classification, Writing Agent, QA checks, Approval tokens, and Mock Publishing."""

import pytest
from pathlib import Path

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.security.approvals import ApprovalService, ApprovalSecurityError
from testkart_intelligence.publishing.guard import assert_live_publishing_disabled, LivePublishingDisabledError
from testkart_intelligence.publishing.mock_publisher import MockPublisher, MockPublishingError
from testkart_intelligence.config import settings


@pytest.fixture
def test_db(tmp_path: Path):
    db_file = tmp_path / "test_stage4.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        conn.execute(
            """
            INSERT INTO official_sources (
                id, code, name, category, state, official_domain, listing_url,
                retrieval_method, verification_status, enabled, consecutive_failures,
                created_at, updated_at
            ) VALUES ('src_upsc', 'UPSC', 'Union Public Service Commission', 'Central', 'Central',
                      'upsc.gov.in', 'https://upsc.gov.in/notices', 'html_scrape', 'VERIFIED', 1, 0,
                      '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES ('not_geo_2026', 'src_upsc', 'Union Public Service Commission', '02/2026-GEOL',
                      'Combined Geo-Scientist Examination 2026', 'https://upsc.gov.in/geo-2026.pdf',
                      'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES ('ver_geo_1', 'not_geo_2026', 1, 'https://upsc.gov.in/geo-2026.pdf', 'hash123',
                      'PDF', '/tmp/geo.pdf', 'Official notification text', 5, '2026-10-24T00:00:00Z')
            """
        )
        facts = [
            ("recruiting_authority", "Union Public Service Commission", "VERIFIED"),
            ("official_source_url", "https://upsc.gov.in/geo-2026.pdf", "VERIFIED"),
            ("notice_number", "02/2026-GEOL", "VERIFIED"),
            ("total_vacancies", "85", "VERIFIED"),
            ("application_start_date", "15/11/2026", "VERIFIED"),
            ("application_end_date", "15/12/2026", "VERIFIED"),
            ("exam_date", "18/02/2027", "VERIFIED"),
            ("eligibility_qualification", "Master's Degree in Geological Science", "VERIFIED"),
            ("age_limit", "21 to 32 years", "VERIFIED"),
            ("application_fee", "Rs. 200 for General/OBC, Nil for SC/ST", "VERIFIED"),
        ]
        for idx, (k, val, st) in enumerate(facts):
            conn.execute(
                """
                INSERT INTO extracted_facts (
                    id, notice_version_id, fact_key, fact_value, confidence,
                    evidence_text, page_number, verified_status, created_at
                ) VALUES (?, 'ver_geo_1', ?, ?, 1.0, ?, 1, ?, '2026-10-24T00:00:00Z')
                """,
                (f"fact_{idx}", k, val, val, st),
            )
    return db_file


def test_notice_classifier():
    """Verify notice classification across diverse announcement types."""
    assert NoticeClassifier.classify("Combined Geo-Scientist Examination 2026 Notification") == NoticeCategory.RECRUITMENT_NOTIFICATION
    assert NoticeClassifier.classify("Corrigendum: Revision in Vacancies for CGL 2026") == NoticeCategory.CORRIGENDUM
    assert NoticeClassifier.classify("Download E-Admit Card for Civil Services Prelims 2026") == NoticeCategory.ADMIT_CARD_RELEASE
    assert NoticeClassifier.classify("Declaration of Final Result for Engineering Services 2025") == NoticeCategory.EXAM_RESULT
    assert NoticeClassifier.classify("Tentative Answer Key and Objection Window for Tier 1") == NoticeCategory.ANSWER_KEY
    assert NoticeClassifier.classify("Examination Schedule for Post Graduate Teacher Exam") == NoticeCategory.EXAM_DATE_ANNOUNCEMENT
    assert NoticeClassifier.classify("Extension of Last Date to Submit Online Application") == NoticeCategory.APPLICATION_WINDOW_UPDATE
    assert NoticeClassifier.classify("Revised Scheme and Syllabus of Examination") == NoticeCategory.SYLLABUS_UPDATE


def test_writing_agent_draft_generation(test_db: Path):
    """Test blog draft generation using verified facts only."""
    writer = WritingAgent(db_path=test_db)
    art_id, art_v_id, content_hash = writer.draft_article(notice_id="not_geo_2026")

    assert art_id.startswith("art_")
    assert art_v_id.startswith("arv_")
    assert len(content_hash) == 64

    # Verify article markdown contents
    with get_db(test_db) as conn:
        row = conn.execute("SELECT content_markdown, title FROM article_versions WHERE id = ?", (art_v_id,)).fetchone()
        md = row["content_markdown"]

        # Verified facts present
        assert "Union Public Service Commission" in md
        assert "02/2026-GEOL" in md
        assert "85" in md
        assert "15/11/2026" in md
        assert "15/12/2026" in md
        assert "https://upsc.gov.in/geo-2026.pdf" in md
        # Lowercase 'k' Testkart branding
        assert "Testkart" in md
        assert "TestKart" not in md


def test_qa_agent_passing_draft(test_db: Path):
    """Verify that a compliant draft with verified links and authority passes QA."""
    writer = WritingAgent(db_path=test_db)
    art_id, art_v_id, _ = writer.draft_article(notice_id="not_geo_2026")

    qa = QualityAssuranceAgent(db_path=test_db)
    passed, score, checks = qa.inspect_and_evaluate(art_v_id)

    assert passed is True
    assert score >= 85.0

    with get_db(test_db) as conn:
        art = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert art["status"] == "QA_PASSED"


def test_qa_agent_blocks_material_violations(test_db: Path):
    """Verify QA blocks drafts that lack official source links or have improper branding."""
    # Insert bad draft without official source link and with improper branding
    bad_art_id = "art_bad"
    bad_v_id = "arv_bad"
    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO blog_articles (id, canonical_notice_id, template_type, status, title, slug, created_at, updated_at)
            VALUES (?, 'not_geo_2026', 'recruitment.md.j2', 'DRAFT', 'Short', 'bad-slug', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """,
            (bad_art_id,),
        )
        conn.execute(
            """
            INSERT INTO article_versions (id, article_id, version_number, content_markdown, content_hash, title, created_at)
            VALUES (?, ?, 1, 'Bad draft content without any official domain link. TestKart error.', 'hash_bad', 'Short', '2026-10-24T00:00:00Z')
            """,
            (bad_v_id, bad_art_id),
        )

    qa = QualityAssuranceAgent(db_path=test_db)
    passed, score, checks = qa.inspect_and_evaluate(bad_v_id)

    assert passed is False
    assert score < 60.0

    with get_db(test_db) as conn:
        art = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (bad_art_id,)).fetchone()
        assert art["status"] == "QA_FAILED"


def test_approval_service_and_single_use_tokens(test_db: Path):
    """Test approval token binding, decision recording, and replay protection."""
    writer = WritingAgent(db_path=test_db)
    art_id, art_v_id, content_hash = writer.draft_article(notice_id="not_geo_2026")

    appr_service = ApprovalService(db_path=test_db)
    record_id, raw_token = appr_service.create_approval_request(
        article_version_id=art_v_id,
        reviewer_email="meettomar07@gmail.com",
    )

    # Approve draft
    result = appr_service.decide_approval(
        raw_token=raw_token,
        decision="APPROVED",
        decision_notes="Verified against official PDF Gazette",
    )
    assert result["decision"] == "APPROVED"

    # Verify article status updated to APPROVED
    with get_db(test_db) as conn:
        art = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert art["status"] == "APPROVED"

    # Replay protection: Attempting to use the same token again must fail
    with pytest.raises(ApprovalSecurityError, match="already been used"):
        appr_service.decide_approval(
            raw_token=raw_token,
            decision="APPROVED",
        )


def test_live_publishing_strictly_disabled():
    """Verify failsafe guard throws error if live publishing is ever attempted."""
    # settings.ALLOW_LIVE_PUBLISHING is False by default
    assert settings.ALLOW_LIVE_PUBLISHING is False
    assert_live_publishing_disabled()  # Does not raise when False

    # Simulate forbidden configuration
    try:
        settings.ALLOW_LIVE_PUBLISHING = True
        with pytest.raises(LivePublishingDisabledError, match="CRITICAL SECURITY VIOLATION"):
            assert_live_publishing_disabled()
    finally:
        settings.ALLOW_LIVE_PUBLISHING = False


def test_mock_publisher_idempotency(test_db: Path):
    """Test mock publisher publishes approved drafts and is idempotent."""
    writer = WritingAgent(db_path=test_db)
    art_id, art_v_id, content_hash = writer.draft_article(notice_id="not_geo_2026")

    appr_service = ApprovalService(db_path=test_db)
    record_id, raw_token = appr_service.create_approval_request(
        article_version_id=art_v_id,
        reviewer_email="meettomar07@gmail.com",
    )
    appr_service.decide_approval(raw_token=raw_token, decision="APPROVED")

    publisher = MockPublisher(db_path=test_db)

    # 1. First publication
    res1 = publisher.publish(
        article_version_id=art_v_id,
        content_hash=content_hash,
        approval_record_id=record_id,
    )
    assert res1["status"] == "COMPLETED"
    assert res1["is_mock"] is True
    assert res1["idempotent"] is False

    # 2. Second publication (idempotent call)
    res2 = publisher.publish(
        article_version_id=art_v_id,
        content_hash=content_hash,
        approval_record_id=record_id,
    )
    assert res2["status"] == "COMPLETED"
    assert res2["idempotent"] is True
    assert res2["job_id"] == res1["job_id"]


def test_mock_publisher_blocks_unapproved_draft(test_db: Path):
    """Verify mock publisher rejects publishing unapproved drafts."""
    writer = WritingAgent(db_path=test_db)
    art_id, art_v_id, content_hash = writer.draft_article(notice_id="not_geo_2026")

    appr_service = ApprovalService(db_path=test_db)
    record_id, raw_token = appr_service.create_approval_request(
        article_version_id=art_v_id,
        reviewer_email="meettomar07@gmail.com",
    )
    # Token created but NOT approved yet (status is PENDING)

    publisher = MockPublisher(db_path=test_db)
    with pytest.raises(MockPublishingError, match="Cannot publish unapproved draft"):
        publisher.publish(
            article_version_id=art_v_id,
            content_hash=content_hash,
            approval_record_id=record_id,
        )
