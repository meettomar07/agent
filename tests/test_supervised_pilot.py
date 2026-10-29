"""Acceptance and regression tests for the Supervised Pilot: Verified Notices to Article Drafts."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.classification.classifier import NoticeCategory
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.editorial.service import EditorialService
from testkart_intelligence.config import settings
from testkart_intelligence.api.app import app


@pytest.fixture
def pilot_test_setup(tmp_path: Path, monkeypatch):
    """Isolated environment with representative pilot sample notices."""
    db_file = tmp_path / "pilot_test.db"
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    monkeypatch.setattr(settings, "DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path)

    init_db(db_file)
    with get_db(db_file) as conn:
        seed_sources_if_empty(conn)

        # 1. SSC JE Revised Exam Dates (Passed Verification)
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
            ) VALUES (
                'cn_ssc_je_dates', 'src_ssc', 'Staff Selection Commission', 'HQ-EC033/7/2025-EC',
                'Important Notice - Revised dates for Junior Engineer Examination, 2026',
                'https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/Important%20notice_revised_dated_26_10_2026.pdf',
                'Central', 'Central', 'EXAM_DATE_ANNOUNCEMENT', 'EXTRACTED',
                '2026-10-26', 'CURRENT', 'NONE', '2026-10-27T06:00:00Z', '2026-10-27T06:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES (
                'ver_ssc_je_dates', 'cn_ssc_je_dates', 1,
                'https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/Important%20notice_revised_dated_26_10_2026.pdf',
                'hash_ssc_dates', 'PDF', 'mock/path.pdf',
                'Junior Engineer Examination 2026 Paper-I Revised proposed dates: 02nd to 06th November, 2026',
                1, '2026-10-27T06:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, evidence_text, page_number, confidence, verified_status, created_at
            ) VALUES 
            ('f1', 'ver_ssc_je_dates', 'recruiting_authority', 'Staff Selection Commission', 'Staff Selection Commission', 1, 1.0, 'VERIFIED', '2026-10-27T06:00:00Z'),
            ('f2', 'ver_ssc_je_dates', 'official_source_url', 'https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/Important%20notice_revised_dated_26_10_2026.pdf', 'https://ssc.gov.in', 1, 1.0, 'VERIFIED', '2026-10-27T06:00:00Z'),
            ('f3', 'ver_ssc_je_dates', 'exam_date', '02nd to 06th November, 2026', '02nd to 06th November, 2026', 1, 0.95, 'VERIFIED', '2026-10-27T06:00:00Z')
            """
        )

        # 2. SSC LDCE Vacancy Table (Missing Application Schedule - Must Fail QA)
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
            ) VALUES (
                'cn_ssc_ldce_vac', 'src_ssc', 'Staff Selection Commission', 'LDCE-2025',
                'Tentative Vacancy of Grade C Stenographers LDCE, 2025',
                'https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/tentative_vacancies_24102026.pdf',
                'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
                '2026-10-24', 'CURRENT', 'NONE', '2026-10-27T06:00:00Z', '2026-10-27T06:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES (
                'ver_ssc_ldce', 'cn_ssc_ldce_vac', 1,
                'https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/tentative_vacancies_24102026.pdf',
                'hash_ssc_ldce', 'PDF', 'mock/path.pdf',
                'Tentative Vacancies for Grade C Stenographers LDCE 2025 Total: 314',
                1, '2026-10-27T06:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, evidence_text, page_number, confidence, verified_status, created_at
            ) VALUES 
            ('f4', 'ver_ssc_ldce', 'recruiting_authority', 'Staff Selection Commission', 'Staff Selection Commission', 1, 1.0, 'VERIFIED', '2026-10-27T06:00:00Z'),
            ('f5', 'ver_ssc_ldce', 'official_source_url', 'https://ssc.gov.in/api/attachment/uploads/masterData/NoticeBoards/tentative_vacancies_24102026.pdf', 'https://ssc.gov.in', 1, 1.0, 'VERIFIED', '2026-10-27T06:00:00Z'),
            ('f6', 'ver_ssc_ldce', 'total_vacancies', '314', 'Total: 314', 1, 0.95, 'VERIFIED', '2026-10-27T06:00:00Z')
            """
        )

        # 3. Scanned PDF (Must Block Automated Drafting)
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, recency_status, triage_flag, first_discovered_at, last_updated_at
            ) VALUES (
                'cn_scanned_notice', 'src_upsc', 'Union Public Service Commission', '11-2026',
                'Clarification for the post of Assistant Public Prosecutor',
                'https://upsc.gov.in/notice_scanned.pdf',
                'Central', 'Central', 'CORRIGENDUM', 'SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW',
                '2026-10-15', 'CURRENT', 'NONE', '2026-10-27T06:00:00Z', '2026-10-27T06:00:00Z'
            )
            """
        )

    return {"db_file": db_file}


def test_pilot_exam_date_drafting_and_qa_pass(pilot_test_setup):
    """Verify that verified exam date announcement generates factual admit card draft and passes QA."""
    writer = WritingAgent(db_path=pilot_test_setup["db_file"])
    qa = QualityAssuranceAgent(db_path=pilot_test_setup["db_file"])

    art_id, art_v_id, content_hash = writer.draft_article("cn_ssc_je_dates")
    assert art_id.startswith("art_")
    assert art_v_id.startswith("arv_")

    passed, score, checks = qa.inspect_and_evaluate(art_v_id)
    assert passed is True
    assert score == 100.0

    # Ensure draft is saved as QA_PASSED or DRAFT, NOT APPROVED
    with get_db(pilot_test_setup["db_file"]) as conn:
        row = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert row["status"] in ("QA_PASSED", "DRAFT")
        assert row["status"] != "APPROVED"


def test_pilot_missing_dates_fails_qa_and_blocks_approval(pilot_test_setup):
    """Verify that a recruitment notice lacking verified application dates fails QA and cannot be approved."""
    writer = WritingAgent(db_path=pilot_test_setup["db_file"])
    qa = QualityAssuranceAgent(db_path=pilot_test_setup["db_file"])

    art_id, art_v_id, content_hash = writer.draft_article("cn_ssc_ldce_vac")
    passed, score, checks = qa.inspect_and_evaluate(art_v_id)

    assert passed is False
    assert score < 85.0
    failed_check_names = [c.rule_name for c in checks if not c.passed]
    assert "rule_recruitment_critical_dates" in failed_check_names

    with get_db(pilot_test_setup["db_file"]) as conn:
        row = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert row["status"] == "QA_FAILED"


def test_pilot_scanned_notice_blocks_drafting(pilot_test_setup):
    """Verify that notices with unreadable/scanned status strictly halt automated article generation."""
    writer = WritingAgent(db_path=pilot_test_setup["db_file"])

    with pytest.raises(ValueError, match="automated drafting halted"):
        writer.draft_article("cn_scanned_notice")
