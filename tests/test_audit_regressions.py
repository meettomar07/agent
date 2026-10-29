"""Regression tests for defects and edge cases discovered during production readiness audit."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
import httpx
from datetime import datetime, timezone, timedelta

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.security.allowlist import (
    validate_official_url,
    extract_domain,
    SecurityValidationError,
)
from testkart_intelligence.discovery.fetcher import (
    SafeFetcher,
    FetchError,
    SoftErrorPageDetected,
)
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.discovery.deduplication import DeduplicationEngine, MatchType
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.security.approvals import ApprovalService, ApprovalSecurityError
from testkart_intelligence.config import settings


@pytest.fixture
def test_db(tmp_path: Path):
    db_file = tmp_path / "test_regressions.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        seed_sources_if_empty(conn)
    return db_file


def test_regression_ssrf_and_credential_rejection():
    """Verify SSRF payloads, embedded credentials, and IP addresses are rejected."""
    # Embedded credentials
    with pytest.raises(SecurityValidationError, match="embedded userinfo"):
        validate_official_url("https://upsc.gov.in:password@attacker.com/evil.pdf")

    with pytest.raises(SecurityValidationError, match="embedded userinfo"):
        validate_official_url("https://admin@upsc.gov.in/test.pdf")

    # IPv4 & IPv6 addresses
    with pytest.raises(SecurityValidationError):
        validate_official_url("http://127.0.0.1/notice.pdf")

    with pytest.raises(SecurityValidationError):
        validate_official_url("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(SecurityValidationError):
        validate_official_url("http://[::1]/notice.pdf")


def test_regression_streaming_size_limit():
    """Verify streaming download aborts when content exceeds maximum allowed size."""
    mock_client = MagicMock()
    mock_client.is_streaming_mock = True

    # Response declaring 100 MB via Content-Length
    mock_resp = MagicMock()
    mock_resp.is_redirect = False
    mock_resp.raise_for_status = MagicMock()
    mock_resp.headers = {"Content-Length": str(100 * 1024 * 1024)}  # 100 MB

    stream_ctx = MagicMock()
    stream_ctx.__enter__.return_value = mock_resp
    stream_ctx.__exit__.return_value = False
    mock_client.stream.return_value = stream_ctx

    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)

    with pytest.raises(FetchError, match="exceeds limit"):
        fetcher.fetch("https://upsc.gov.in/oversized.pdf")


def test_regression_soft_404_error_page_detection():
    """Verify soft-404 redirects (e.g. FileNotFound.aspx, error.aspx) raise SoftErrorPageDetected."""
    mock_client = MagicMock()

    # Simulates an ASP.NET server redirecting to FileNotFound.aspx with HTTP 200
    mock_resp = MagicMock()
    mock_resp.is_redirect = False
    mock_resp.raise_for_status = MagicMock()
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.iter_bytes.return_value = [b"<html><body>404 The resource cannot be found.</body></html>"]

    stream_ctx = MagicMock()
    stream_ctx.__enter__.return_value = mock_resp
    stream_ctx.__exit__.return_value = False
    mock_client.stream.return_value = stream_ctx

    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)

    with pytest.raises(SoftErrorPageDetected, match="soft error page"):
        fetcher.fetch("https://uppsc.up.nic.in/FileNotFound.aspx?aspxerrorpath=/Notice.aspx")


def test_regression_ssc_multi_date_range_and_narrative_vacancies():
    """Verify standard SSC and UPSC multi-date ranges and narrative vacancies are extracted."""
    ssc_page_text = (
        "STAFF SELECTION COMMISSION\n"
        "Notice No. 3/1/2026-P&P-I\n"
        "Dates for submission of online applications: 24.06.2026 to 24.07.2026\n"
        "Last date and time for receipt of online applications: 24.07.2026 (23:00)\n"
        "Schedule of Tier-I (Computer Based Examination): Sep-Oct, 2026\n"
        "Total Vacancies: 17,727\n"
        "Minimum Educational Qualification: Bachelor's Degree from a recognized University\n"
        "Application Fee: Fee payable: Rs 100/- (Rs one hundred only)\n"
        "Age Limit: 18-30 years\n"
    )

    pages = [{"page_number": 1, "text": ssc_page_text}]
    facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name="Staff Selection Commission",
        notice_title="Combined Graduate Level Examination 2026",
        official_url="https://ssc.gov.in/cgl.pdf",
    )

    fact_map = {f.key: f for f in facts}
    assert "application_start_date" in fact_map
    assert fact_map["application_start_date"].value == "24.06.2026"
    assert "application_end_date" in fact_map
    assert fact_map["application_end_date"].value == "24.07.2026"
    assert "total_vacancies" in fact_map
    assert fact_map["total_vacancies"].value == "17727"
    assert "exam_date" in fact_map


def test_regression_article_status_reset_on_revision(test_db: Path):
    """Verify drafting version 2 resets article status to DRAFT even if version 1 was APPROVED."""
    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, title, normalized_url,
                category, state, status, first_discovered_at, last_updated_at
            ) VALUES ('not_rev_test', 'src_upsc', 'UPSC', 'Civil Services 2026',
                      'https://upsc.gov.in/cse.pdf', 'Central', 'Central', 'EXTRACTED', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES ('ver_rev_1', 'not_rev_test', 1, 'https://upsc.gov.in/cse.pdf', 'hash1', 'PDF', '/tmp/doc.pdf', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES ('f1', 'ver_rev_1', 'recruiting_authority', 'UPSC', 1.0, 'VERIFIED', '2026-10-24T00:00:00Z')
            """
        )

    writer = WritingAgent(db_path=test_db)
    art_id, v1_id, hash1 = writer.draft_article("not_rev_test")

    # Simulate human editor approving version 1
    with get_db(test_db) as conn:
        conn.execute("UPDATE blog_articles SET status = 'APPROVED' WHERE id = ?", (art_id,))

    # Now simulate version 2 arriving (revised notice)
    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES ('ver_rev_2', 'not_rev_test', 2, 'https://upsc.gov.in/cse.pdf', 'hash2', 'PDF', '/tmp/doc2.pdf', '2026-10-25T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES ('f2', 'ver_rev_2', 'recruiting_authority', 'UPSC', 1.0, 'VERIFIED', '2026-10-25T00:00:00Z')
            """
        )

    # Draft version 2
    art_id2, v2_id, hash2 = writer.draft_article("not_rev_test", notice_version_id="ver_rev_2")

    # CRITICAL: Verify article status is RESET to 'DRAFT' and NOT left as 'APPROVED'!
    with get_db(test_db) as conn:
        art = conn.execute("SELECT status, current_version_id FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert art["status"] == "DRAFT"
        assert art["current_version_id"] == v2_id


def test_regression_orphaned_scan_recovery_on_startup(test_db: Path):
    """Verify that crashed/orphaned scans marked RUNNING are recovered to FAILED on startup."""
    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO scan_runs (id, scan_type, status, started_at, sources_checked, notices_found, errors_count)
            VALUES ('scan_crashed', 'SCHEDULED', 'RUNNING', '2026-10-20T00:00:00Z', 5, 0, 0)
            """
        )

    # Initializing DiscoveryEngine must recover orphaned scan
    engine = DiscoveryEngine(db_path=test_db)

    with get_db(test_db) as conn:
        scan = conn.execute("SELECT status, error_summary FROM scan_runs WHERE id = 'scan_crashed'").fetchone()
        assert scan["status"] == "FAILED"
        assert "Process terminated" in scan["error_summary"]


def test_regression_token_invalidation_on_content_change(test_db: Path):
    """Verify approval token is invalidated if article content is modified after token generation."""
    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, title, normalized_url,
                category, state, status, first_discovered_at, last_updated_at
            ) VALUES ('not_tamper_test', 'src_upsc', 'UPSC', 'Tamper Notice 2026',
                      'https://upsc.gov.in/tamper.pdf', 'Central', 'Central', 'EXTRACTED', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES ('ver_tamper_1', 'not_tamper_test', 1, 'https://upsc.gov.in/tamper.pdf', 'hash_orig', 'PDF', '/tmp/doc.pdf', '2026-10-24T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES ('f_tamper', 'ver_tamper_1', 'recruiting_authority', 'UPSC', 1.0, 'VERIFIED', '2026-10-24T00:00:00Z')
            """
        )

    writer = WritingAgent(db_path=test_db)
    art_id, v1_id, hash1 = writer.draft_article("not_tamper_test")

    # Generate approval token bound to v1
    appr_service = ApprovalService(db_path=test_db)
    rec_id, raw_token = appr_service.create_approval_request(
        article_version_id=v1_id,
        reviewer_email="meettomar07@gmail.com",
    )

    # Tamper with the article version's content hash directly in the database
    with get_db(test_db) as conn:
        conn.execute("UPDATE article_versions SET content_hash = 'tampered_hash_value' WHERE id = ?", (v1_id,))

    # Attempting to approve must fail with content hash mismatch and invalidate token
    with pytest.raises(ApprovalSecurityError, match="Content hash mismatch"):
        appr_service.decide_approval(raw_token=raw_token, decision="APPROVED")

    with get_db(test_db) as conn:
        record = conn.execute("SELECT status FROM approval_records WHERE id = ?", (rec_id,)).fetchone()
        assert record["status"] == "INVALIDATED"
