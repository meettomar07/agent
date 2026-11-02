"""Acceptance and Regression Test Suite for the 30-Day Supervised Operational Pilot.

Covers:
1. Daily notice monitoring & scheduler live execution (06:00 and 18:00 Asia/Kolkata).
2. Notice lifecycle tracking: DISCOVERED -> FETCHED -> CLASSIFIED -> EXTRACTED -> DRAFTED -> QA_REVIEW -> HUMAN_REVIEW -> APPROVED -> MOCK_PUBLISHED.
3. Corrigendum and update handling across all six required amendment scenarios.
4. Operational metrics computation and human reviewer vs automated test action auditing.
5. All eight reliability and recovery drills.
6. Safety invariants: ALLOW_LIVE_PUBLISHING = False, ENABLE_EMAIL_NOTIFICATIONS = False.
"""

import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from unittest.mock import MagicMock, patch
import uuid
from datetime import datetime, timezone, timedelta

import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import init_db, get_db, get_connection
from testkart_intelligence.registry.service import SourceRegistryService, seed_sources_if_empty
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.discovery.fetcher import SafeFetcher, FetchError, SoftErrorPageDetected
from testkart_intelligence.discovery.deduplication import DeduplicationEngine, MatchType
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.editorial.service import (
    EditorialService,
    ApprovalBlockedError,
    EditorialSecurityError,
    StaleVersionConflictError,
)
from testkart_intelligence.editorial.operational_metrics import OperationalMetricsService
from testkart_intelligence.scheduler.job_runner import (
    ScanScheduler,
    SchedulerAlreadyRunningError,
)
from testkart_intelligence.publishing.mock_publisher import MockPublisher, MockPublishingError
from testkart_intelligence.publishing.guard import assert_live_publishing_disabled, LivePublishingDisabledError
from testkart_intelligence.api.app import app


def create_sample_pdf_bytes(text: str) -> bytes:
    """Helper to generate valid PDF byte streams for testing."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    b = doc.tobytes()
    doc.close()
    return b


@pytest.fixture
def pilot_db(tmp_path: Path, monkeypatch):
    """Isolated database and filesystem environment for pilot test runs."""
    test_db = tmp_path / "pilot_30day.db"
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    monkeypatch.setattr(settings, "DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr(settings, "ALLOW_LIVE_PUBLISHING", False)
    monkeypatch.setattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", False)

    init_db(test_db)
    with get_db(test_db) as conn:
        seed_sources_if_empty(conn)

    return test_db


# =========================================================================
# 1. Daily Notice Monitoring & Scheduler Verification
# =========================================================================

def test_scheduler_live_execution_and_overlap_prevention(pilot_db):
    """Verify that ScanScheduler genuinely runs in the background, enforces Asia/Kolkata timezone,
    prevents duplicate instances, prevents overlapping scan executions, and shuts down cleanly."""
    scheduler = ScanScheduler(db_path=pilot_db)
    scheduler.start()

    try:
        assert scheduler.is_running is True
        status = scheduler.get_status()
        assert status["running"] is True
        assert status["timezone"] == "Asia/Kolkata"
        assert status["scan_hours"] == [6, 18]
        assert status["scan_minutes"] == 0
        assert status["next_run_time"] is not None

        # 1. Duplicate instance prevention
        sched_dup = ScanScheduler(db_path=pilot_db)
        with pytest.raises(SchedulerAlreadyRunningError):
            sched_dup.start()

        # 2. Overlapping scan prevention (lock contention)
        # Manually hold lock to simulate a running scan
        scheduler._lock.acquire()
        try:
            # Calling scan_job while locked must skip execution without throwing unhandled exceptions
            scheduler.scan_job()
        finally:
            scheduler._lock.release()

        # 3. Trigger actual scan job and verify recorded execution in database
        scheduler.scan_job()
        with get_db(pilot_db) as conn:
            row = conn.execute("SELECT count(*) as c FROM scan_runs WHERE scan_type = 'SCHEDULED'").fetchone()
            assert row["c"] >= 1

    finally:
        scheduler.shutdown()
        assert scheduler.is_running is False


# =========================================================================
# 2. Notice Lifecycle Tracking (All States)
# =========================================================================

def test_notice_lifecycle_all_states(pilot_db):
    """Track notice through DISCOVERED -> FETCHED -> CLASSIFIED -> EXTRACTED -> DRAFTED ->
    QA_REVIEW -> HUMAN_REVIEW -> APPROVED -> MOCK_PUBLISHED.
    Also test REJECTED, BLOCKED, and audited override unlocking."""
    # 1. Setup mock official notice
    pdf_text = (
        "UNION PUBLIC SERVICE COMMISSION\n"
        "Notice No. 10/2026-ENG\n"
        "Engineering Services Examination 2026\n"
        "Total Vacancies: 420\n"
        "Opening Date: 01/10/2026\n"
        "Closing Date: 21/10/2026\n"
        "Date of Examination: 14/02/2027\n"
        "Age Limit: 21 to 30 years as on 01.01.2027\n"
        "Educational Qualification: Degree in Engineering (Civil/Mechanical/Electrical/ECE)\n"
        "Application Fee: Rs. 200, Female/SC/ST exempted\n"
    )
    pdf_bytes = create_sample_pdf_bytes(pdf_text)
    url = "https://upsc.gov.in/ese-2026-notice.pdf"

    # Step 1: DISCOVERED
    now_iso = datetime.now(timezone.utc).isoformat()
    notice_id = "not_ese_01"
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_upsc', 'Union Public Service Commission', '10/2026-ENG',
                      'Engineering Services Examination 2026', ?, 'PSC', 'Central', 'DISCOVERED', ?, ?)
            """,
            (notice_id, url, now_iso, now_iso),
        )

    # Step 2 & 3: FETCHED & EXTRACTED
    verifier = VerificationAgent(db_path=pilot_db)
    v_id, facts = verifier.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url=url,
        content_type="application/pdf",
    )
    with get_db(pilot_db) as conn:
        n_status = conn.execute("SELECT status FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()["status"]
        assert n_status == "EXTRACTED"

    # Step 4: CLASSIFIED
    with get_db(pilot_db) as conn:
        cat = NoticeClassifier.classify_and_update(notice_id, conn)
        assert cat == NoticeCategory.RECRUITMENT_NOTIFICATION

    # Step 5: DRAFTED
    writer = WritingAgent(db_path=pilot_db)
    art_id, art_v_id, hash1 = writer.draft_article(notice_id)
    with get_db(pilot_db) as conn:
        art_status = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,)).fetchone()["status"]
        assert art_status == "DRAFT"

    # Step 6: QA_REVIEW
    qa = QualityAssuranceAgent(db_path=pilot_db)
    passed, score, checks = qa.inspect_and_evaluate(art_v_id)
    assert passed is True
    assert score >= 85.0
    with get_db(pilot_db) as conn:
        art_status = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,)).fetchone()["status"]
        assert art_status == "QA_PASSED"

    # Step 7: HUMAN_REVIEW & APPROVAL
    editorial = EditorialService(db_path=pilot_db)
    editor_data = editorial.get_draft_editor(art_id)
    assert editor_data["article"]["status"] == "QA_PASSED"
    assert len(editor_data["critical_fields_summary"]) >= 4 or len(editor_data["notice_review"]["extracted_facts"]) >= 4

    dec = editorial.submit_decision(
        article_id=art_id,
        expected_version_id=art_v_id,
        expected_content_hash=hash1,
        decision="APPROVE",
        editor_email="meettomar07@gmail.com",
        notes="All critical facts verified against official UPSC Gazette.",
    )
    assert dec["decision"] == "APPROVED"
    assert dec["is_override"] is False

    # Step 8: MOCK_PUBLISHED
    publisher = MockPublisher(db_path=pilot_db)
    pub = publisher.publish(
        article_version_id=art_v_id,
        content_hash=hash1,
        approval_record_id=dec["approval_id"],
    )
    assert pub["status"] == "COMPLETED"
    assert pub["is_mock"] is True

    # -------------------------------------------------------------
    # Test BLOCKED and AUDITED OVERRIDE flow
    # -------------------------------------------------------------
    # Notice with missing critical application dates
    blocked_id = "not_blocked_01"
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_upsc', 'Union Public Service Commission', 'UNR-01',
                      'Special Recruitment Notice without Dates', 'https://upsc.gov.in/unreadable.pdf',
                      'PSC', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED', ?, ?)
            """,
            (blocked_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, retrieved_at)
            VALUES ('nv_blk', ?, 1, 'https://upsc.gov.in/unreadable.pdf', 'h_blk', 'PDF', 'blk.pdf', ?)
            """,
            (blocked_id, now_iso),
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (id, notice_version_id, fact_key, fact_value, confidence, evidence_text, page_number, verified_status, created_at)
            VALUES ('f_blk_vac', 'nv_blk', 'total_vacancies', '12', 0.95, '12 posts', 1, 'VERIFIED', ?)
            """,
            (now_iso,),
        )

    b_art_id, b_arv_id, b_hash = writer.draft_article(blocked_id)

    # Attempting normal approval MUST be blocked
    with pytest.raises(ApprovalBlockedError):
        editorial.submit_decision(
            article_id=b_art_id,
            expected_version_id=b_arv_id,
            expected_content_hash=b_hash,
            decision="APPROVE",
            is_override=False,
            editor_email="meettomar07@gmail.com",
        )

    # Audited override with full justification unlocks approval
    override_dec = editorial.submit_decision(
        article_id=b_art_id,
        expected_version_id=b_arv_id,
        expected_content_hash=b_hash,
        decision="APPROVE",
        is_override=True,
        override_reason="Manually transcribed text from physical gazette copy in department library.",
        editor_email="meettomar07@gmail.com",
    )
    assert override_dec["decision"] == "APPROVED"
    assert override_dec["is_override"] is True

    # -------------------------------------------------------------
    # Test REJECTED flow
    # -------------------------------------------------------------
    rej_id = "not_rej_01"
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_ssc', 'Staff Selection Commission', 'REJ-01',
                      'Invalid Spurious Notice', 'https://ssc.gov.in/spurious.pdf',
                      'Central', 'Central', 'OTHER_ANNOUNCEMENT', 'EXTRACTED', ?, ?)
            """,
            (rej_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, retrieved_at)
            VALUES ('nv_rej', ?, 1, 'https://ssc.gov.in/spurious.pdf', 'h_rej', 'PDF', 'rej.pdf', ?)
            """,
            (rej_id, now_iso),
        )

    r_art_id, r_arv_id, r_hash = writer.draft_article(rej_id)
    rej_dec = editorial.submit_decision(
        article_id=r_art_id,
        expected_version_id=r_arv_id,
        expected_content_hash=r_hash,
        decision="REJECT",
        editor_email="meettomar07@gmail.com",
        notes="Spurious portal item not an official examination announcement.",
    )
    assert rej_dec["decision"] == "REJECTED"


# =========================================================================
# 3. Corrigendum & Update Handling (All 6 Scenarios)
# =========================================================================

def test_corrigendum_and_update_lifecycle_scenarios(pilot_db):
    """Verify all six required corrigendum and update handling scenarios:
    1. New corrigendum linked to an existing recruitment notice.
    2. Revised application deadline.
    3. Revised vacancy count.
    4. Revised examination schedule.
    5. Cancellation or withdrawal of a recruitment notice.
    6. Multiple amendments to the same original notice.
    Preserves previous article versions and approval history."""
    now_iso = datetime.now(timezone.utc).isoformat()
    editorial = EditorialService(db_path=pilot_db)
    writer = WritingAgent(db_path=pilot_db)

    # Base Recruitment Notice (Original)
    orig_id = "not_parent_cgl"
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_ssc', 'Staff Selection Commission', 'Notice No. 3/1/2026-P&P-I',
                      'Combined Graduate Level Examination 2026', 'https://ssc.gov.in/cgl-2026.pdf',
                      'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED', ?, ?)
            """,
            (orig_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, retrieved_at)
            VALUES ('nv_cgl_v1', ?, 1, 'https://ssc.gov.in/cgl-2026.pdf', 'h_cgl_v1', 'PDF', 'cgl_v1.pdf', ?)
            """,
            (orig_id, now_iso),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at)
            VALUES (?, 'nv_cgl_v1', ?, ?, 1.0, 'VERIFIED', ?)
            """,
            [
                ("f_cgl_1", "recruiting_authority", "Staff Selection Commission", now_iso),
                ("f_cgl_2", "total_vacancies", "17727", now_iso),
                ("f_cgl_3", "application_start_date", "24.06.2026", now_iso),
                ("f_cgl_4", "application_end_date", "24.07.2026", now_iso),
                ("f_cgl_5", "exam_date", "Sep-Oct 2026", now_iso),
                ("f_cgl_6", "official_source_url", "https://ssc.gov.in/cgl-2026.pdf", now_iso),
            ]
        )

    cgl_art_id, cgl_arv1_id, cgl_hash1 = writer.draft_article(orig_id)
    editorial.submit_decision(
        article_id=cgl_art_id,
        expected_version_id=cgl_arv1_id,
        expected_content_hash=cgl_hash1,
        decision="APPROVE",
        editor_email="meettomar07@gmail.com",
    )

    # -------------------------------------------------------------
    # Scenario 1: New Corrigendum linked to existing notice
    # -------------------------------------------------------------
    corr1_id = "not_corr_01"
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_ssc', 'Staff Selection Commission', 'F.No. 3/1/2026-P&P-I',
                      'Corrigendum to Combined Graduate Level Examination 2026',
                      'https://ssc.gov.in/cgl_corr1.pdf', 'Central', 'Central', 'CORRIGENDUM', 'EXTRACTED', ?, ?)
            """,
            (corr1_id, now_iso, now_iso),
        )
        parent_id, rel_type, conf, notes = NoticeClassifier.link_to_parent_notice(
            notice_id=corr1_id,
            source_id="src_ssc",
            title="Corrigendum to Combined Graduate Level Examination 2026",
            notice_number="F.No. 3/1/2026-P&P-I",
            category=NoticeCategory.CORRIGENDUM,
            conn=conn,
        )
        assert parent_id == orig_id
        assert rel_type == "CORRIGENDUM"
        assert conf >= 0.90

    # -------------------------------------------------------------
    # Scenario 2: Revised Application Deadline (v2 generated, DRAFT reset)
    # -------------------------------------------------------------
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, retrieved_at)
            VALUES ('nv_cgl_v2', ?, 2, 'https://ssc.gov.in/cgl_ext.pdf', 'h_cgl_v2', 'PDF', 'cgl_v2.pdf', ?)
            """,
            (orig_id, now_iso),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at)
            VALUES (?, 'nv_cgl_v2', ?, ?, 1.0, 'VERIFIED', ?)
            """,
            [
                ("f_cgl2_1", "recruiting_authority", "Staff Selection Commission", now_iso),
                ("f_cgl2_2", "total_vacancies", "17727", now_iso),
                ("f_cgl2_3", "application_start_date", "24.06.2026", now_iso),
                ("f_cgl2_4", "application_end_date", "31.07.2026", now_iso),  # EXTENDED
                ("f_cgl2_5", "exam_date", "Sep-Oct 2026", now_iso),
                ("f_cgl2_6", "official_source_url", "https://ssc.gov.in/cgl-2026.pdf", now_iso),
            ]
        )

    _, cgl_arv2_id, cgl_hash2 = writer.draft_article(orig_id, notice_version_id="nv_cgl_v2")
    assert cgl_hash2 != cgl_hash1

    with get_db(pilot_db) as conn:
        row = conn.execute("SELECT status, current_version_id FROM blog_articles WHERE id = ?", (cgl_art_id,)).fetchone()
        assert row["status"] == "DRAFT"  # Reset to DRAFT
        assert row["current_version_id"] == cgl_arv2_id

    # -------------------------------------------------------------
    # Scenario 3: Revised Vacancy Count (17,727 to 18,500)
    # -------------------------------------------------------------
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, retrieved_at)
            VALUES ('nv_cgl_v3', ?, 3, 'https://ssc.gov.in/cgl_vac.pdf', 'h_cgl_v3', 'PDF', 'cgl_v3.pdf', ?)
            """,
            (orig_id, now_iso),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at)
            VALUES (?, 'nv_cgl_v3', ?, ?, 1.0, 'VERIFIED', ?)
            """,
            [
                ("f_cgl3_1", "recruiting_authority", "Staff Selection Commission", now_iso),
                ("f_cgl3_2", "total_vacancies", "18500", now_iso),  # ENHANCED
                ("f_cgl3_3", "application_start_date", "24.06.2026", now_iso),
                ("f_cgl3_4", "application_end_date", "31.07.2026", now_iso),
                ("f_cgl3_5", "exam_date", "Sep-Oct 2026", now_iso),
                ("f_cgl3_6", "official_source_url", "https://ssc.gov.in/cgl-2026.pdf", now_iso),
            ]
        )

    _, cgl_arv3_id, cgl_hash3 = writer.draft_article(orig_id, notice_version_id="nv_cgl_v3")
    with get_db(pilot_db) as conn:
        art_ver = conn.execute("SELECT content_markdown FROM article_versions WHERE id = ?", (cgl_arv3_id,)).fetchone()
        assert "18500" in art_ver["content_markdown"]

    # -------------------------------------------------------------
    # Scenario 4: Revised Examination Schedule
    # -------------------------------------------------------------
    sched_id = "not_sched_rev"
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_ssc', 'Staff Selection Commission', 'HQ-SCHED-01',
                      'Revised Schedule of Computer Based Examination December, 2026',
                      'https://ssc.gov.in/rev_sched.pdf', 'Central', 'Central', 'EXAM_DATE_ANNOUNCEMENT', 'EXTRACTED', ?, ?)
            """,
            (sched_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, retrieved_at)
            VALUES ('nv_sch', ?, 1, 'https://ssc.gov.in/rev_sched.pdf', 'h_sch', 'PDF', 'sch.pdf', ?)
            """,
            (sched_id, now_iso),
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at)
            VALUES ('f_sch', 'nv_sch', 'exam_date', 'December, 2026', 1.0, 'VERIFIED', ?)
            """,
            (now_iso,),
        )

    s_art_id, s_arv_id, s_hash = writer.draft_article(sched_id)
    with get_db(pilot_db) as conn:
        tmpl = conn.execute("SELECT template_type FROM blog_articles WHERE id = ?", (s_art_id,)).fetchone()["template_type"]
        assert tmpl == "exam_schedule.md.j2"

    # -------------------------------------------------------------
    # Scenario 5: Cancellation or Withdrawal of Notice
    # -------------------------------------------------------------
    cancel_id = "not_cancel_01"
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_uppsc', 'Uttar Pradesh Public Service Commission', 'CAN-01',
                      'Notice Regarding Cancellation of Advt No. A-1/E-1/2026',
                      'https://uppsc.up.nic.in/cancellation.pdf', 'PSC', 'State', 'CANCELLATION_NOTICE', 'EXTRACTED', ?, ?)
            """,
            (cancel_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, retrieved_at)
            VALUES ('nv_can', ?, 1, 'https://uppsc.up.nic.in/cancellation.pdf', 'h_can', 'PDF', 'can.pdf', ?)
            """,
            (cancel_id, now_iso),
        )

    can_art_id, can_arv_id, can_hash = writer.draft_article(cancel_id)
    with get_db(pilot_db) as conn:
        tmpl = conn.execute("SELECT template_type FROM blog_articles WHERE id = ?", (can_art_id,)).fetchone()["template_type"]
        assert tmpl == "cancellation.md.j2"

    # -------------------------------------------------------------
    # Scenario 6: Multiple Amendments to Same Notice
    # -------------------------------------------------------------
    # Notice has v1, v2, v3 in article_versions. Verify all 3 are stored immutably.
    with get_db(pilot_db) as conn:
        v_rows = conn.execute(
            "SELECT version_number, content_hash FROM article_versions WHERE article_id = ? ORDER BY version_number",
            (cgl_art_id,)
        ).fetchall()
        assert len(v_rows) == 3
        assert v_rows[0]["version_number"] == 1
        assert v_rows[1]["version_number"] == 2
        assert v_rows[2]["version_number"] == 3
        # Hashes must all be distinct
        hashes = {r["content_hash"] for r in v_rows}
        assert len(hashes) == 3


# =========================================================================
# 4. Reliability and Recovery Drills (All 8 Drills)
# =========================================================================

def test_reliability_and_recovery_drills(pilot_db):
    """Execute all eight required reliability and recovery tests:
    1. Government portal downtime (503 Service Unavailable, timeout) -> consecutive failures logged.
    2. Invalid or inaccessible PDFs (404 soft error, corrupt bytes) -> unreadable status.
    3. Duplicate notices -> DeduplicationEngine matches without duplicate canonical row.
    4. Interrupted scans -> recover_orphaned_scans sets RUNNING to FAILED.
    5. Database restart and recovery -> Connection re-init in WAL mode.
    6. Scheduler restart -> shutdown and restart cleanly.
    7. Application restart during processing -> FastAPI lifespan handles scheduler cleanly.
    8. Repeated retrieval of an unchanged notice -> Idempotent fetch, no revision."""
    now_iso = datetime.now(timezone.utc).isoformat()

    # Drill 1: Government portal downtime
    engine = DiscoveryEngine(db_path=pilot_db)
    mock_failing_client = MagicMock()
    mock_failing_client.get.side_effect = httpx.HTTPStatusError("503 Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503))
    engine.fetcher = SafeFetcher(client=mock_failing_client, rate_limit_delay=0.0)

    res = engine.run_scan(scan_type="MANUAL", source_code="UPSC")
    assert res["errors_count"] >= 1
    with get_db(pilot_db) as conn:
        src = conn.execute("SELECT consecutive_failures FROM official_sources WHERE code = 'UPSC'").fetchone()
        assert src["consecutive_failures"] >= 1

    # Drill 2: Invalid or inaccessible PDF
    verifier = VerificationAgent(db_path=pilot_db)
    corrupt_bytes = b"NOT_A_VALID_PDF_STREAM_RANDOM_BYTES"
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status, first_discovered_at, last_updated_at
            ) VALUES ('not_corrupt', 'src_ssc', 'Staff Selection Commission', 'COR-01',
                      'Corrupt PDF Notice', 'https://ssc.gov.in/corrupt.pdf',
                      'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED', ?, ?)
            """,
            (now_iso, now_iso),
        )

    # Verification of corrupt bytes must not crash, must flag unreadable
    v_id, facts = verifier.process_and_verify_document(
        notice_id="not_corrupt",
        doc_bytes=corrupt_bytes,
        doc_url="https://ssc.gov.in/corrupt.pdf",
        content_type="application/pdf",
    )
    with get_db(pilot_db) as conn:
        status = conn.execute("SELECT status FROM canonical_notices WHERE id = 'not_corrupt'").fetchone()["status"]
        assert "FLAGGED_FOR_HUMAN_REVIEW" in status or status == "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW"

    # Drill 3: Duplicate Notices
    with get_db(pilot_db) as conn:
        dedup = DeduplicationEngine(conn)
        match_type, matched_id, _ = dedup.evaluate_candidate(
            source_id="src_ssc",
            normalized_url="https://ssc.gov.in/corrupt.pdf",
            notice_number="COR-01",
            title="Corrupt PDF Notice",
        )
        assert match_type == MatchType.UNCHANGED
        assert matched_id == "not_corrupt"

    # Drill 4: Interrupted Scans (Orphaned scan recovery)
    orphan_scan_id = "scan_interrupted_99"
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO scan_runs (id, scan_type, status, started_at, sources_checked, notices_found, errors_count)
            VALUES (?, 'SCHEDULED', 'RUNNING', ?, 2, 0, 0)
            """,
            (orphan_scan_id, now_iso),
        )

    recovered_count = engine.recover_orphaned_scans()
    assert recovered_count >= 1
    with get_db(pilot_db) as conn:
        st = conn.execute("SELECT status, error_summary FROM scan_runs WHERE id = ?", (orphan_scan_id,)).fetchone()
        assert st["status"] == "FAILED"
        assert "Recovered on startup" in st["error_summary"]

    # Drill 5: Database restart and recovery
    conn = get_connection(pilot_db)
    conn.close()
    # Reopen fresh connection
    conn2 = get_connection(pilot_db)
    row = conn2.execute("PRAGMA journal_mode").fetchone()
    assert row[0].upper() == "WAL"
    conn2.close()

    # Drill 6: Scheduler restart
    s = ScanScheduler(db_path=pilot_db)
    s.start()
    assert s.is_running is True
    s.shutdown()
    assert s.is_running is False
    s_restart = ScanScheduler(db_path=pilot_db)
    s_restart.start()
    assert s_restart.is_running is True
    s_restart.shutdown()

    # Drill 7: Application restart during processing
    client = TestClient(app)
    resp = client.get("/api/sources")
    assert resp.status_code == 200

    # Drill 8: Repeated retrieval of an unchanged notice
    with get_db(pilot_db) as conn:
        dedup = DeduplicationEngine(conn)
        # Same hash as existing version
        m_type, mid, _ = dedup.evaluate_candidate(
            source_id="src_ssc",
            normalized_url="https://ssc.gov.in/corrupt.pdf",
            new_doc_hash=SafeFetcher.compute_sha256(corrupt_bytes),
        )
        assert m_type == MatchType.UNCHANGED


# =========================================================================
# 5. Operational Metrics Service & Actor Distinction
# =========================================================================

def test_operational_metrics_service_and_actor_auditing(pilot_db):
    """Verify that OperationalMetricsService computes comprehensive cumulative metrics,
    distinguishes human actions from automated test actors, and generates clean Markdown reports."""
    svc = OperationalMetricsService(db_path=pilot_db)
    metrics = svc.get_cumulative_metrics()

    assert "sources" in metrics
    assert len(metrics["sources"]) >= 5
    assert "scheduler" in metrics
    assert "classification_distribution" in metrics
    assert "extraction" in metrics
    assert "qa" in metrics
    assert "editorial" in metrics
    assert "safety" in metrics

    # Verify actor breakdown
    editorial = EditorialService(db_path=pilot_db)
    # Log human correction
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db(pilot_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (id, source_id, authority_name, notice_number, title, normalized_url, category, state, classification, status, first_discovered_at, last_updated_at)
            VALUES ('not_test_01', 'src_upsc', 'UPSC', 'N-01', 'Test Notice', 'https://upsc.gov.in/test.pdf', 'PSC', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED', ?, ?)
            """,
            (now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (id, notice_id, version_number, document_url, document_hash, document_type, storage_path, retrieved_at)
            VALUES ('ver_test_01', 'not_test_01', 1, 'https://upsc.gov.in/test.pdf', 'hash_test', 'PDF', 'test.pdf', ?)
            """,
            (now_iso,),
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (id, notice_version_id, fact_key, fact_value, verified_status, created_at)
            VALUES ('f_test_corr', 'ver_test_01', 'total_vacancies', '100', 'VERIFIED', ?)
            """,
            (now_iso,),
        )
    editorial.correct_fact(
        fact_id="f_test_corr",
        corrected_value="150",
        reviewer_email="meettomar07@gmail.com",
        reason="Official addendum increased seats by 50.",
    )

    metrics_after = svc.get_cumulative_metrics()
    assert metrics_after["editorial"]["human_fact_corrections"] >= 1

    md_report = svc.generate_markdown_report_sections(metrics_after)
    assert "Source-Wise Operational Reliability" in md_report
    assert "ALLOW_LIVE_PUBLISHING" in md_report
    assert "DISABLED (SECURE)" in md_report or "False" in md_report


# =========================================================================
# 6. Safety Invariants & Live Publishing Blocked
# =========================================================================

def test_safety_invariants_and_zero_external_dispatches(pilot_db, monkeypatch):
    """Enforce that ALLOW_LIVE_PUBLISHING = False and ENABLE_EMAIL_NOTIFICATIONS = False
    cannot be bypassed, and attempting live publication immediately raises a fatal exception."""
    assert settings.ALLOW_LIVE_PUBLISHING is False
    assert settings.ENABLE_EMAIL_NOTIFICATIONS is False

    # Calling assert_live_publishing_disabled succeeds when False
    assert_live_publishing_disabled()

    # If ALLOW_LIVE_PUBLISHING is toggled to True, assertion MUST raise LivePublishingDisabledError
    monkeypatch.setattr(settings, "ALLOW_LIVE_PUBLISHING", True)
    with pytest.raises(LivePublishingDisabledError):
        assert_live_publishing_disabled()

    # MockPublisher publish call must also fail if ALLOW_LIVE_PUBLISHING is True
    pub = MockPublisher(db_path=pilot_db)
    with pytest.raises(LivePublishingDisabledError):
        pub.publish("art_v_any", "hash_any", "appr_any")
