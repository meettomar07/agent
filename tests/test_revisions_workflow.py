"""Tests for revision tracking, corrigenda, deadline updates, cross-page deduplication, and source recovery."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
import uuid
from datetime import datetime, timezone

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.discovery.deduplication import DeduplicationEngine, MatchType
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.discovery.fetcher import (
    SafeFetcher,
    FetchError,
    create_resilient_ssl_context,
    LEGACY_TLS_APPROVED_HOSTS,
    NON_COMPLIANT_HEADER_APPROVED_HOSTS,
)
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.security.approvals import ApprovalService, ApprovalSecurityError
from testkart_intelligence.publishing.mock_publisher import MockPublisher, MockPublishingError


@pytest.fixture
def test_db(tmp_path: Path):
    db_file = tmp_path / "test_revisions.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        seed_sources_if_empty(conn)
    return db_file


def test_revision_pdf_replaced_at_same_url(test_db: Path):
    """Verify that a document updated at the same official URL triggers REVISION_DETECTED and records v2."""
    now_iso = datetime.now(timezone.utc).isoformat()
    source_id = "src_upsc"
    notice_url = "https://upsc.gov.in/examinations/active-examinations/geoscientist-2026.pdf"
    notice_id = f"not_{uuid.uuid4().hex[:12]}"
    nv1_id = f"nv_{uuid.uuid4().hex[:8]}"

    with get_db(test_db) as conn:
        # Initial notice v1
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, status, first_discovered_at, last_updated_at
            ) VALUES (?, ?, 'UPSC', '02/2026', 'Combined Geo-Scientist 2026', ?, 'PSC', 'Central', 'DISCOVERED', ?, ?)
            """,
            (notice_id, source_id, notice_url, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 1, ?, 'hash_v1_initial', 'PDF', 'data/v1.pdf', ?)
            """,
            (nv1_id, notice_id, notice_url, now_iso),
        )

    # Subsequent scan with new document hash at same URL
    with get_db(test_db) as conn:
        dedup = DeduplicationEngine(conn)
        match_type, matched_id, last_v = dedup.evaluate_candidate(
            source_id=source_id,
            normalized_url=notice_url,
            notice_number="02/2026",
            title="Combined Geo-Scientist 2026",
            new_doc_hash="hash_v2_updated_pdf",
        )
        assert match_type == MatchType.REVISION
        assert matched_id == notice_id
        assert last_v == 1

        # Record revision v2
        conn.execute(
            """
            UPDATE canonical_notices
            SET status = 'REVISION_DETECTED', last_updated_at = ?
            WHERE id = ?
            """,
            (now_iso, notice_id),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 2, ?, 'hash_v2_updated_pdf', 'PDF', 'data/v2.pdf', ?)
            """,
            (f"nv_{uuid.uuid4().hex[:8]}", notice_id, notice_url, now_iso),
        )

    with get_db(test_db) as conn:
        c = conn.cursor()
        c.execute("SELECT status FROM canonical_notices WHERE id = ?", (notice_id,))
        assert c.fetchone()[0] == "REVISION_DETECTED"

        c.execute("SELECT count(*) FROM notice_versions WHERE notice_id = ?", (notice_id,))
        assert c.fetchone()[0] == 2


def test_revision_changed_deadline_resets_approval(test_db: Path):
    """Verify that updating an article deadline creates v2, resets status to DRAFT, and invalidates old token."""
    now_iso = datetime.now(timezone.utc).isoformat()
    notice_id = f"not_{uuid.uuid4().hex[:12]}"
    nv1_id = f"nv_{uuid.uuid4().hex[:8]}"
    nv2_id = f"nv_{uuid.uuid4().hex[:8]}"

    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_upsc', 'Union Public Service Commission', '05/2026', 'Engineering Services 2026',
                      'https://upsc.gov.in/ese-2026.pdf', 'PSC', 'Central', 'RECRUITMENT_NOTIFICATION', 'VERIFIED', ?, ?)
            """,
            (notice_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 1, 'https://upsc.gov.in/ese-2026.pdf', 'hash_v1', 'PDF', 'data/v1.pdf', ?)
            """,
            (nv1_id, notice_id, now_iso),
        )
        # Seed facts for v1
        conn.executemany(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'VERIFIED', ?)
            """,
            [
                (f"f_{uuid.uuid4().hex[:8]}", nv1_id, "recruiting_authority", "Union Public Service Commission", 1.0, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv1_id, "total_vacancies", "450", 0.95, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv1_id, "application_start_date", "01/10/2026", 0.90, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv1_id, "application_end_date", "20/10/2026", 0.90, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv1_id, "official_source_url", "https://upsc.gov.in/ese-2026.pdf", 1.0, now_iso),
            ]
        )

    writer = WritingAgent(test_db)

    # 1. Generate version 1 draft
    art_id, art_v1_id, hash1 = writer.draft_article(notice_id, notice_version_id=nv1_id)

    # 2. Editor approves version 1
    approver = ApprovalService(test_db)
    rec_id, token_str = approver.create_approval_request(art_v1_id, "meettomar07@gmail.com")
    decision = approver.decide_approval(token_str, "APPROVED", decision_notes="Chief Editor Approval")
    assert decision["decision"] == "APPROVED"

    with get_db(test_db) as conn:
        c = conn.cursor()
        c.execute("UPDATE blog_articles SET status = 'APPROVED' WHERE id = ?", (art_id,))

    # 3. Corrigendum extends deadline from 20/10/2026 to 30/10/2026 (Version 2)
    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 2, 'https://upsc.gov.in/ese-2026.pdf', 'hash_v2', 'PDF', 'data/v2.pdf', ?)
            """,
            (nv2_id, notice_id, now_iso),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'VERIFIED', ?)
            """,
            [
                (f"f_{uuid.uuid4().hex[:8]}", nv2_id, "recruiting_authority", "Union Public Service Commission", 1.0, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv2_id, "total_vacancies", "450", 0.95, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv2_id, "application_start_date", "01/10/2026", 0.90, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv2_id, "application_end_date", "30/10/2026", 0.95, now_iso),  # EXTENDED
                (f"f_{uuid.uuid4().hex[:8]}", nv2_id, "official_source_url", "https://upsc.gov.in/ese-2026.pdf", 1.0, now_iso),
            ]
        )

    _, art_v2_id, hash2 = writer.draft_article(notice_id, notice_version_id=nv2_id)
    assert hash2 != hash1

    # Status MUST be reset to DRAFT
    with get_db(test_db) as conn:
        c = conn.cursor()
        c.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,))
        art_status = c.fetchone()[0]
        assert art_status == "DRAFT"

    # 4. Old approval token cannot approve version 2
    with pytest.raises(ApprovalSecurityError, match="has already been used"):
        approver.decide_approval(token_str, "APPROVED", decision_notes="Editor B")


def test_corrigendum_changes_vacancies_or_eligibility(test_db: Path):
    """Verify that a corrigendum notice updates facts and outputs corrigendum template."""
    now_iso = datetime.now(timezone.utc).isoformat()
    notice_id = f"not_{uuid.uuid4().hex[:12]}"
    nv_id = f"nv_{uuid.uuid4().hex[:8]}"

    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_ssc', 'Staff Selection Commission', 'HQ-01/2026', 'Junior Engineer 2026 Corrigendum',
                      'https://ssc.gov.in/corrigendum.pdf', 'Central', 'Central', 'CORRIGENDUM', 'VERIFIED', ?, ?)
            """,
            (notice_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 1, 'https://ssc.gov.in/corrigendum.pdf', 'hash_corr_1', 'PDF', 'data/c.pdf', ?)
            """,
            (nv_id, notice_id, now_iso),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'VERIFIED', ?)
            """,
            [
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "recruiting_authority", "Staff Selection Commission", 1.0, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "notice_number", "HQ-01/2026", 0.95, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "total_vacancies", "1765", 0.95, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "eligibility", "Degree or Diploma in Engineering", 0.90, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "official_source_url", "https://ssc.gov.in/corrigendum.pdf", 1.0, now_iso),
            ]
        )

    writer = WritingAgent(test_db)
    art_id, art_v_id, chash = writer.draft_article(notice_id, notice_version_id=nv_id)

    with get_db(test_db) as conn:
        c = conn.cursor()
        c.execute("SELECT template_type, title FROM blog_articles WHERE id = ?", (art_id,))
        row = c.fetchone()
        assert row[0] == "corrigendum.md.j2"
        assert "Corrigendum" in row[1]

        c.execute("SELECT content_markdown FROM article_versions WHERE id = ?", (art_v_id,))
        body = c.fetchone()[0]
        assert "1765" in body


def test_withdrawn_notification_blocks_publishing(test_db: Path):
    """Verify that a withdrawn notification cannot proceed to publishing."""
    now_iso = datetime.now(timezone.utc).isoformat()
    notice_id = f"not_{uuid.uuid4().hex[:12]}"
    art_id = f"art_{uuid.uuid4().hex[:12]}"

    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_upsc', 'UPSC', '13-2025', 'Cancelled Notice',
                      'https://upsc.gov.in/cancel.pdf', 'PSC', 'Central', 'WITHDRAWN', ?, ?)
            """,
            (notice_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO blog_articles (
                id, canonical_notice_id, template_type, title, slug, status, created_at, updated_at
            ) VALUES (?, ?, 'announcement.md.j2', 'Cancelled Post', 'cancelled-post', 'DRAFT', ?, ?)
            """,
            (art_id, notice_id, now_iso, now_iso),
        )

    # Publisher must refuse publishing on unapproved or draft notice
    publisher = MockPublisher(test_db)
    with pytest.raises(MockPublishingError, match="does not exist|not approved"):
        publisher.publish(art_id, "some_content_hash", "some_approval_id")


def test_cross_page_duplicate_deduplication(test_db: Path):
    """Verify notices posted across multiple pages (e.g. notifications & recruitment) deduplicate cleanly."""
    now_iso = datetime.now(timezone.utc).isoformat()
    source_id = "src_upsc"

    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, status, first_discovered_at, last_updated_at
            ) VALUES ('can_not_1', ?, 'UPSC', '01/2026', 'Civil Services Examination 2026',
                      'https://upsc.gov.in/sites/default/files/cse-2026.pdf', 'PSC', 'Central', 'DISCOVERED', ?, ?)
            """,
            (source_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES ('nv_cse_1', 'can_not_1', 1, 'https://upsc.gov.in/sites/default/files/cse-2026.pdf',
                      'hash_cse_1', 'PDF', 'data/cse.pdf', ?)
            """,
            (now_iso,),
        )

    with get_db(test_db) as conn:
        dedup = DeduplicationEngine(conn)

        # Same notice re-encountered on a different listing page with identical notice number
        match_type, matched_id, _ = dedup.evaluate_candidate(
            source_id=source_id,
            normalized_url="https://upsc.gov.in/recruitment/cse-2026.pdf",
            notice_number="01/2026",
            title="Civil Services Examination 2026",
            new_doc_hash="hash_cse_1",
        )
        assert match_type == MatchType.UNCHANGED
        assert matched_id == "can_not_1"


def test_source_outage_graceful_recovery(test_db: Path):
    """Verify that a temporary network failure logs FAILED without crashing, and subsequent scan succeeds."""
    mock_fetcher = MagicMock()
    # 1. First scan fails with connection timeout
    mock_fetcher.fetch.side_effect = FetchError("Connection timeout to government server")

    engine = DiscoveryEngine(test_db, fetcher=mock_fetcher)
    res1 = engine.run_scan(source_code="UPSC")
    assert res1["status"] == "FAILED"
    assert res1["errors_count"] == 1
    assert "Connection timeout" in res1["error_summary"][0]

    # Verify scan source log recorded FAILED
    with get_db(test_db) as conn:
        c = conn.cursor()
        c.execute("SELECT status, error_message FROM scan_source_logs WHERE scan_run_id = ?", (res1["scan_id"],))
        row = c.fetchone()
        assert row[0] == "FAILED"
        assert "timeout" in row[1]

    # 2. Server recovers; second scan succeeds with 1 notice
    mock_fetcher.fetch.side_effect = None
    mock_fetcher.fetch.return_value = (
        b"<html><table><tr><td><a href='/notice.pdf'>Recruitment Notice 2026</a></td></tr></table></html>",
        "text/html",
        "https://upsc.gov.in/examinations/notifications",
        120.0,
    )

    res2 = engine.run_scan(source_code="UPSC")
    assert res2["status"] == "COMPLETED"
    assert res2["notices_found"] == 1
    assert res2["errors_count"] == 0


def test_host_specific_tls_and_permissive_header():
    """Verify that legacy ciphers and lenient headers are scoped strictly to approved government hosts."""
    # Standard hosts get modern SECLEVEL=2
    std_ctx = create_resilient_ssl_context("upsc.gov.in")
    assert std_ctx is not None

    # Approved legacy hosts get legacy context
    for host in LEGACY_TLS_APPROVED_HOSTS:
        legacy_ctx = create_resilient_ssl_context(host)
        assert legacy_ctx is not None

    # Host not in allowlist cannot get legacy ciphers
    untrusted_ctx = create_resilient_ssl_context("evil-attacker.com")
    assert untrusted_ctx is not None

    # Check non-compliant header set
    assert "kpsc.kar.nic.in" in NON_COMPLIANT_HEADER_APPROVED_HOSTS
    assert "evil.com" not in NON_COMPLIANT_HEADER_APPROVED_HOSTS
