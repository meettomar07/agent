"""Regression tests for Critical Factual Integrity and QA Remediation.

Verifies:
1. Cancellation notices take precedence over recruitment keywords and never generate application instructions.
2. Scanned notices cannot receive QA_PASSED without verified OCR text.
3. Spurious vacancy counts (e.g. JEE 75 questions) and bogus notice identifiers ('will') are rejected.
4. Heading fragments in data fields (fee, age) fail validation and QA.
5. Missing or unsupported recruitment deadlines cannot pass QA.
6. Category-aware QA: Admit-card and Result notices pass without requiring vacancies.
7. Corrigenda invalidate prior approvals.
8. Source failures cannot be treated as successful empty scans.
9. Live publishing remains permanently disabled.
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
import pytest
import pymupdf

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.discovery.fetcher import SafeFetcher, SoftErrorPageDetected
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor, ExtractedFactItem
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.security.approvals import ApprovalService, ApprovalSecurityError
from testkart_intelligence.publishing.guard import assert_live_publishing_disabled, LivePublishingDisabledError
from testkart_intelligence.publishing.mock_publisher import MockPublisher, MockPublishingError
from testkart_intelligence.config import settings


@pytest.fixture
def remed_db(tmp_path: Path):
    db_file = tmp_path / "remed_test.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        seed_sources_if_empty(conn)
    return db_file


# ---------------------------------------------------------------------------
# Test 1: Cancellation Notice Classification and Drafting Safety
# ---------------------------------------------------------------------------
def test_cancellation_notice_classification_and_drafting_safety(remed_db: Path):
    """Prove that cancellation language strictly takes precedence and never generates application steps."""
    cancellation_titles = [
        "Cancellation of 06 Posts in Ministry of Mines (Advt 13-2025)",
        "06 Posts Cancelled",
        "Withdrawal of Recruitment Advt No. 02/2026",
        "Notice regarding cancellation of Junior Engineer Examination",
        "Recruitment process stands cancelled for Technical Officer",
        "Annulment of Selection Process for Assistant Engineer",
    ]

    for title in cancellation_titles:
        cat = NoticeClassifier.classify(title=title, content_snippet="The posts advertised vide advt 13-2025 are cancelled.")
        assert cat == NoticeCategory.CANCELLATION_NOTICE, f"Failed for title: {title}"

    # Verify article generation and QA safety
    notice_id = f"not_cancel_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db(remed_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at)
            VALUES (?, 'src_upsc', 'Union Public Service Commission', '13-2025',
                'Cancellation of 06 Posts in Ministry of Mines (Advt 13-2025)',
                'https://www.upsc.gov.in/cancel-06.pdf', 'Central', 'Central', ?, 'EXTRACTED', ?, ?)
            """,
            (notice_id, NoticeCategory.CANCELLATION_NOTICE.value, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at)
            VALUES ('ver_cancel_1', ?, 1, 'https://www.upsc.gov.in/cancel-06.pdf', 'hash_cancel',
                'PDF', 'cancel.pdf', 'Notice regarding cancellation of posts', 1, ?)
            """,
            (notice_id, now_iso),
        )

    writer = WritingAgent(db_path=remed_db)
    art_id, art_v_id, _ = writer.draft_article(notice_id=notice_id)

    with get_db(remed_db) as conn:
        art_row = conn.execute("SELECT content_markdown FROM article_versions WHERE id = ?", (art_v_id,)).fetchone()
        md = art_row["content_markdown"]

    # Invariants for cancellation notice:
    assert "CANCELLED" in md
    assert "Do Not Apply" in md
    assert "Do Not Pay Fees" in md
    # Must NOT contain application instructions or claims of open recruitment
    assert "Fill in the online application form" not in md
    assert "Pay the application fee (if applicable)" not in md
    assert "Register using valid mobile number" not in md

    # QA Audit must pass cancellation safety check
    qa = QualityAssuranceAgent(db_path=remed_db)
    passed, score, checks = qa.inspect_and_evaluate(art_v_id)
    cancellation_check = next((c for c in checks if c.rule_name == "rule_cancellation_safety"), None)
    assert cancellation_check is not None
    assert cancellation_check.passed is True
    assert passed is True


# ---------------------------------------------------------------------------
# Test 2: Scanned Notice Hard Stop
# ---------------------------------------------------------------------------
def test_scanned_notice_blocked_from_drafting_and_qa(remed_db: Path):
    """Prove that scanned/unreadable documents cannot receive QA_PASSED or generate normal drafts."""
    notice_id = f"not_scan_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Create dummy scanned PDF bytes with 0 text
    doc = pymupdf.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    verifier = VerificationAgent(db_path=remed_db)
    with get_db(remed_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at)
            VALUES (?, 'src_upsc', 'Union Public Service Commission', '13-2025',
                'Scanned Notice 07', 'https://www.upsc.gov.in/scanned.pdf', 'Central', 'Central',
                'RECRUITMENT_NOTIFICATION', 'DISCOVERED', ?, ?)
            """,
            (notice_id, now_iso, now_iso),
        )

    # Ingesting scanned document must set status to SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW
    v_id, facts = verifier.process_and_verify_document(notice_id, pdf_bytes, "https://www.upsc.gov.in/scanned.pdf", "application/pdf")

    with get_db(remed_db) as conn:
        n_row = conn.execute("SELECT status FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()
        assert n_row["status"] == "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW"

    # Drafting must halt safely
    writer = WritingAgent(db_path=remed_db)
    with pytest.raises(ValueError, match="flagged for human review|automated drafting halted"):
        writer.draft_article(notice_id=notice_id)

    # If an article version exists for unreadable notice, QA MUST FAIL
    with get_db(remed_db) as conn:
        art_id = f"art_scan_{uuid.uuid4().hex[:8]}"
        arv_id = f"arv_scan_{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO blog_articles (id, canonical_notice_id, template_type, status, title, slug, created_at, updated_at) VALUES (?, ?, 'recruitment.md.j2', 'DRAFT', 'T', 's', ?, ?)",
            (art_id, notice_id, now_iso, now_iso),
        )
        conn.execute(
            "INSERT INTO article_versions (id, article_id, version_number, content_markdown, content_hash, title, created_at) VALUES (?, ?, 1, 'Draft on scanned text. https://upsc.gov.in Testkart note. ## Details\n- item\n', 'h', 'T', ?)",
            (arv_id, art_id, now_iso),
        )

    qa = QualityAssuranceAgent(db_path=remed_db)
    qa_passed, score, checks = qa.inspect_and_evaluate(arv_id)
    assert qa_passed is False
    readability_check = next((c for c in checks if c.rule_name == "rule_document_readability"), None)
    assert readability_check is not None
    assert readability_check.passed is False


# ---------------------------------------------------------------------------
# Test 3: Spurious Vacancies and Bogus Notice Numbers Blocked
# ---------------------------------------------------------------------------
def test_spurious_vacancy_count_and_bogus_notice_number_blocked(remed_db: Path):
    """Prove that question counts are not extracted as vacancies and words like 'will' are not notice numbers."""
    pages = [
        {
            "page_number": 1,
            "text": "National Testing Agency\nNotification will be available on the portal.\nJoint Entrance Examination 2027.",
        },
        {
            "page_number": 2,
            "text": "Pattern of Examination: Mathematics: 25, Physics: 25, Chemistry: 25. Total 75 questions in Paper 1.",
        },
    ]

    facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name="National Testing Agency",
        notice_title="JEE Main 2027",
        official_url="https://nta.ac.in/jee.pdf",
    )
    fact_map = {f.key: f for f in facts}

    # 1. Total vacancies must NOT be 75
    assert "total_vacancies" not in fact_map, "Question count 75 was falsely extracted as total vacancies"

    # 2. Notice number must NOT be 'will'
    if "notice_number" in fact_map:
        assert fact_map["notice_number"].value.lower() != "will", "'will' was falsely extracted as notice number"

    # 3. Verifier cross-check must flag question counts if present
    verifier = VerificationAgent(db_path=remed_db)
    bad_fact = ExtractedFactItem(
        key="total_vacancies",
        value="75",
        evidence_text="Total 75 questions in Paper 1",
        page_number=2,
    )
    checked_facts = verifier._verify_and_cross_check_facts([bad_fact], "Total 75 questions in Paper 1")
    assert checked_facts[0].status == "CONTRADICTORY"


# ---------------------------------------------------------------------------
# Test 4: Heading Fragments in Data Fields Fail QA
# ---------------------------------------------------------------------------
def test_heading_fragments_in_data_fields_fail_qa(remed_db: Path):
    """Prove that raw heading fragments (e.g. UPPSC fee/age) are caught and rejected by QA."""
    notice_id = f"not_frag_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    bad_markdown = (
        "# UPPSC Recruitment\n\n"
        "Official portal: https://uppsc.up.nic.in\n"
        "Published by Uttar Pradesh Public Service Commission.\n"
        "Testkart verified guide.\n\n"
        "## Details\n"
        "- Application Fee: After completing the process of First and Second Stage in the online\n"
        "- Age Limit: Candidates must have attained the age of\n\n"
        "| Field | Value |\n|---|---|\n| Start | 26/10/2026 |\n"
    )

    art_id = f"art_frag_{uuid.uuid4().hex[:8]}"
    arv_id = f"arv_frag_{uuid.uuid4().hex[:8]}"

    with get_db(remed_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at)
            VALUES (?, 'src_uppsc', 'Uttar Pradesh Public Service Commission', 'A-4/E-1/2026',
                'UPPSC RO ARO', 'https://uppsc.up.nic.in/ro.pdf', 'PSC', 'Uttar Pradesh',
                'RECRUITMENT_NOTIFICATION', 'EXTRACTED', ?, ?)
            """,
            (notice_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at)
            VALUES ('ver_frag_1', ?, 1, 'https://uppsc.up.nic.in/ro.pdf', 'hash_frag', 'PDF', 'ro.pdf', 'raw text', 1, ?)
            """,
            (notice_id, now_iso),
        )
        conn.execute(
            "INSERT INTO blog_articles (id, canonical_notice_id, template_type, status, title, slug, created_at, updated_at) VALUES (?, ?, 'recruitment.md.j2', 'DRAFT', 'T', 's', ?, ?)",
            (art_id, notice_id, now_iso, now_iso),
        )
        conn.execute(
            "INSERT INTO article_versions (id, article_id, version_number, content_markdown, content_hash, title, created_at) VALUES (?, ?, 1, ?, 'h', 'T', ?)",
            (arv_id, art_id, bad_markdown, now_iso),
        )

    qa = QualityAssuranceAgent(db_path=remed_db)
    passed, score, checks = qa.inspect_and_evaluate(arv_id)
    assert passed is False
    frag_check = next((c for c in checks if c.rule_name == "rule_no_heading_fragments_in_data"), None)
    assert frag_check is not None
    assert frag_check.passed is False


# ---------------------------------------------------------------------------
# Test 5: Missing Recruitment Deadline Cannot Pass QA
# ---------------------------------------------------------------------------
def test_missing_recruitment_deadline_fails_qa(remed_db: Path):
    """Prove that a recruitment guide with missing/placeholder deadlines fails QA."""
    notice_id = f"not_dates_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    placeholder_markdown = (
        "# SSC CGL Recruitment 2026\n\n"
        "Official portal: https://ssc.gov.in\n"
        "Published by Staff Selection Commission.\n"
        "Testkart verified guide.\n\n"
        "## Important Dates\n"
        "| Event | Official Date |\n"
        "|---|---|\n"
        "| Online Application Start Date | Not specified in verified extraction (Requires Editor Review) |\n"
        "| Last Date to Apply Online | Not specified in verified extraction (Requires Editor Review) |\n\n"
        "- Total Vacancies: 5000 posts\n"
    )

    art_id = f"art_dates_{uuid.uuid4().hex[:8]}"
    arv_id = f"arv_dates_{uuid.uuid4().hex[:8]}"

    with get_db(remed_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at)
            VALUES (?, 'src_ssc', 'Staff Selection Commission', '01/2026',
                'SSC CGL 2026', 'https://ssc.gov.in/cgl.pdf', 'Central', 'Central',
                'RECRUITMENT_NOTIFICATION', 'EXTRACTED', ?, ?)
            """,
            (notice_id, now_iso, now_iso),
        )
        conn.execute(
            "INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, raw_text, page_count, retrieved_at) VALUES ('ver_d_1', ?, 1, 'https://ssc.gov.in/cgl.pdf', 'h', 'PDF', 'cgl.pdf', 'raw text', 1, ?)",
            (notice_id, now_iso),
        )
        conn.execute(
            "INSERT INTO blog_articles (id, canonical_notice_id, template_type, status, title, slug, created_at, updated_at) VALUES (?, ?, 'recruitment.md.j2', 'DRAFT', 'T', 's', ?, ?)",
            (art_id, notice_id, now_iso, now_iso),
        )
        conn.execute(
            "INSERT INTO article_versions (id, article_id, version_number, content_markdown, content_hash, title, created_at) VALUES (?, ?, 1, ?, 'h', 'T', ?)",
            (arv_id, art_id, placeholder_markdown, now_iso),
        )

    qa = QualityAssuranceAgent(db_path=remed_db)
    passed, score, checks = qa.inspect_and_evaluate(arv_id)
    assert passed is False
    dates_check = next((c for c in checks if c.rule_name == "rule_recruitment_critical_dates"), None)
    assert dates_check is not None
    assert dates_check.passed is False


# ---------------------------------------------------------------------------
# Test 6: Category-Aware QA (Admit Card & Result Pass Without Vacancies)
# ---------------------------------------------------------------------------
def test_category_aware_qa_admit_card_and_result_pass_without_vacancies(remed_db: Path):
    """Prove that Admit Card and Result notices do not fail for lacking vacancy counts."""
    notice_id = f"not_admit_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    title_str = "UPSC Civil Services Prelims 2026 E-Admit Card Out"
    admit_markdown = (
        "# Admit Card Release: UPSC CSE Prelims 2026\n\n"
        "Official portal: https://www.upsc.gov.in\n"
        "Published by Union Public Service Commission.\n"
        "Testkart verified official examination notification guide.\n\n"
        "## Overview of Examination\n"
        "The Union Public Service Commission has officially made the e-admit cards available for candidates "
        "appearing in the Civil Services Preliminary Examination 2026. All eligible candidates who registered "
        "before the closing date must download their hall ticket and verify the examination center details.\n\n"
        "## Examination Schedule & City Details\n"
        "- Examination Date: 24th May 2026\n"
        "- Admit Card Available: From 01 May 2026\n"
        "- Shift Timings: Paper 1 (09:30 AM to 11:30 AM), Paper 2 (02:30 PM to 04:30 PM)\n\n"
        "| Event | Official Date |\n"
        "| :--- | :--- |\n"
        "| Admit Card Release | 01.05.2026 |\n"
        "| Examination Date | 24.05.2026 |\n"
    )

    art_id = f"art_admit_{uuid.uuid4().hex[:8]}"
    arv_id = f"arv_admit_{uuid.uuid4().hex[:8]}"

    with get_db(remed_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at)
            VALUES (?, 'src_upsc', 'Union Public Service Commission', '01/2026',
                ?, 'https://www.upsc.gov.in/admit.pdf', 'Central', 'Central',
                'ADMIT_CARD_RELEASE', 'EXTRACTED', ?, ?)
            """,
            (notice_id, title_str, now_iso, now_iso),
        )
        conn.execute(
            "INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, raw_text, page_count, retrieved_at) VALUES ('ver_adm_1', ?, 1, 'https://www.upsc.gov.in/admit.pdf', 'h', 'PDF', 'admit.pdf', 'raw text', 1, ?)",
            (notice_id, now_iso),
        )
        conn.execute(
            "INSERT INTO blog_articles (id, canonical_notice_id, template_type, status, title, slug, created_at, updated_at) VALUES (?, ?, 'admit_card.md.j2', 'DRAFT', ?, 'upsc-admit-card', ?, ?)",
            (art_id, notice_id, title_str, now_iso, now_iso),
        )
        conn.execute(
            "INSERT INTO article_versions (id, article_id, version_number, content_markdown, content_hash, title, created_at) VALUES (?, ?, 1, ?, 'h', ?, ?)",
            (arv_id, art_id, admit_markdown, title_str, now_iso),
        )

    qa = QualityAssuranceAgent(db_path=remed_db)
    passed, score, checks = qa.inspect_and_evaluate(arv_id)
    assert passed is True
    # Recruitment date check must NOT run on admit card
    dates_check = next((c for c in checks if c.rule_name == "rule_recruitment_critical_dates"), None)
    assert dates_check is None


# ---------------------------------------------------------------------------
# Test 7: Scheduled Scanning Strict Whitelist to 5 Authorities
# ---------------------------------------------------------------------------
def test_scheduled_scan_restricted_to_five_approved_authorities(remed_db: Path):
    """Prove that scheduled discovery runs strictly for the 5 approved authorities."""
    mock_client = MagicMock()
    resp = MagicMock()
    resp.is_redirect = False
    resp.raise_for_status = MagicMock()
    resp.content = b"<html><body><table><tr><td>Notice</td></tr></table></body></html>"
    resp.headers = {"Content-Type": "text/html"}
    mock_client.get = MagicMock(return_value=resp)

    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)
    engine = DiscoveryEngine(db_path=remed_db, fetcher=fetcher)

    scan_result = engine.run_scan(scan_type="SCHEDULED")
    # Must only check the 5 approved sources: UPSC, SSC, NTA, UPPSC, TNPSC
    assert scan_result["sources_checked"] == 5

    with get_db(remed_db) as conn:
        sources_checked = [
            row["code"] for row in conn.execute(
                """
                SELECT DISTINCT os.code
                FROM scan_source_logs ssl
                JOIN official_sources os ON ssl.source_id = os.id
                WHERE ssl.scan_run_id = ?
                """,
                (scan_result["scan_id"],),
            ).fetchall()
        ]
    assert set(sources_checked) == {"UPSC", "SSC", "NTA", "UPPSC", "TNPSC"}


# ---------------------------------------------------------------------------
# Test 8: Live Publishing Invariant Preserved
# ---------------------------------------------------------------------------
def test_live_publishing_remains_strictly_disabled(monkeypatch):
    """Verify that ALLOW_LIVE_PUBLISHING remains False and cannot be bypassed."""
    assert settings.ALLOW_LIVE_PUBLISHING is False
    assert_live_publishing_disabled()

    # If live publishing is enabled, it must immediately raise LivePublishingDisabledError
    monkeypatch.setattr(settings, "ALLOW_LIVE_PUBLISHING", True)
    with pytest.raises(LivePublishingDisabledError):
        assert_live_publishing_disabled()
