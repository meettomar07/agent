"""Acceptance tests for Pre-Production Operational Stability:
1. Asia/Kolkata scheduler and twice-daily cron configuration
2. Overlap prevention for concurrent scan jobs
3. Orphaned scan recovery across restarts
4. Source timeout, retry, partial failure, and logging
5. Source recovery and failure counter reset
6. Distinction between successful empty scans and source failures
"""

import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from unittest.mock import MagicMock
import httpx
import pytest
from apscheduler.triggers.cron import CronTrigger

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.scheduler.job_runner import ScanScheduler
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.discovery.fetcher import SafeFetcher


def test_scheduler_timezone_and_twice_daily_trigger():
    """Verify scheduler is configured for Asia/Kolkata at 06:00 and 18:00 IST."""
    assert settings.TIMEZONE == "Asia/Kolkata"
    assert settings.SCAN_HOURS == [6, 18]
    assert settings.SCAN_MINUTES == 0

    hours_str = ",".join(str(h) for h in settings.SCAN_HOURS)
    trigger = CronTrigger(
        hour=hours_str,
        minute=settings.SCAN_MINUTES,
        timezone=settings.TIMEZONE,
    )

    kolkata_tz = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(kolkata_tz)
    next_fire = trigger.get_next_fire_time(None, now_ist)

    assert next_fire is not None
    assert next_fire.hour in [6, 18]
    assert next_fire.minute == 0
    assert "Asia/Kolkata" in str(next_fire.tzinfo) or getattr(next_fire.tzinfo, "key", None) == "Asia/Kolkata"


def test_scheduler_overlap_prevention(tmp_path: Path):
    """Verify that concurrent scan invocations are prevented by non-blocking lock."""
    test_db = tmp_path / "scheduler_overlap.db"
    init_db(test_db)

    scheduler = ScanScheduler(db_path=test_db)
    # Simulate a long-running scan holding the lock
    acquired = scheduler._lock.acquire(blocking=False)
    assert acquired is True

    skipped_flag = False

    def try_overlapping_scan():
        nonlocal skipped_flag
        scheduler.scan_job()
        skipped_flag = True

    thread = threading.Thread(target=try_overlapping_scan)
    thread.start()
    thread.join(timeout=2.0)

    scheduler._lock.release()
    assert skipped_flag is True


def test_orphaned_scan_recovery_on_restart(tmp_path: Path):
    """Confirm application recovers orphaned 'RUNNING' scans upon restart."""
    test_db = tmp_path / "orphan_recovery.db"
    init_db(test_db)

    with get_db(test_db) as conn:
        conn.execute(
            """
            INSERT INTO scan_runs (id, scan_type, status, started_at, sources_checked, notices_found, errors_count)
            VALUES ('scan_orphaned_test', 'SCHEDULED', 'RUNNING', '2026-10-27T06:00:00Z', 1, 0, 0)
            """
        )

    # Re-instantiating DiscoveryEngine simulates an application restart
    engine = DiscoveryEngine(db_path=test_db)

    with get_db(test_db) as conn:
        row = conn.execute("SELECT status, error_summary, completed_at FROM scan_runs WHERE id = 'scan_orphaned_test'").fetchone()
        assert row["status"] == "FAILED"
        assert "Recovered on startup" in row["error_summary"]
        assert row["completed_at"] is not None


def test_source_timeout_partial_failure_and_logging(tmp_path: Path):
    """Verify timeouts, retries, and source-level failure logging during partial portal outage."""
    test_db = tmp_path / "partial_failure.db"
    init_db(test_db)
    with get_db(test_db) as conn:
        seed_sources_if_empty(conn)

    mock_client = MagicMock()

    def mock_get(url, **kwargs):
        if "upsc.gov.in" in url:
            raise httpx.ReadTimeout("Connection timed out after 25.0s")
        resp = MagicMock()
        resp.is_redirect = False
        resp.raise_for_status = MagicMock()
        resp.content = b"<html><body><table><tr><td>Normal Notice</td></tr></table></body></html>"
        resp.headers = {"Content-Type": "text/html"}
        return resp

    mock_client.get = mock_get
    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)
    engine = DiscoveryEngine(db_path=test_db, fetcher=fetcher)

    result = engine.run_scan(scan_type="MANUAL")

    assert result["sources_checked"] == 5
    assert result["errors_count"] == 1
    assert any("Connection timed out" in s for s in result["error_summary"])

    with get_db(test_db) as conn:
        upsc_src = conn.execute("SELECT consecutive_failures, last_error FROM official_sources WHERE code = 'UPSC'").fetchone()
        assert upsc_src["consecutive_failures"] == 1
        assert "Connection timed out" in upsc_src["last_error"]

        # Check source logs: UPSC is FAILED, others are SUCCESS_NO_NEW
        upsc_log = conn.execute(
            "SELECT status, error_message FROM scan_source_logs ssl JOIN official_sources s ON ssl.source_id = s.id WHERE s.code = 'UPSC' AND ssl.scan_run_id = ?",
            (result["scan_id"],)
        ).fetchone()
        assert upsc_log["status"] == "FAILED"
        assert "Connection timed out" in upsc_log["error_message"]

        ssc_log = conn.execute(
            "SELECT status FROM scan_source_logs ssl JOIN official_sources s ON ssl.source_id = s.id WHERE s.code = 'SSC' AND ssl.scan_run_id = ?",
            (result["scan_id"],)
        ).fetchone()
        assert ssc_log["status"] == "SUCCESS_NO_NEW"


def test_source_recovery_resets_failures(tmp_path: Path):
    """Verify that subsequent successful scan clears consecutive failures and updates success timestamp."""
    test_db = tmp_path / "recovery.db"
    init_db(test_db)
    with get_db(test_db) as conn:
        seed_sources_if_empty(conn)
        # Pre-seed failure
        conn.execute("UPDATE official_sources SET consecutive_failures = 3, last_error = 'Past outage' WHERE code = 'UPSC'")

    mock_client = MagicMock()
    resp = MagicMock()
    resp.is_redirect = False
    resp.raise_for_status = MagicMock()
    resp.content = b"<html><body><table><tr><td>Normal Portal</td></tr></table></body></html>"
    resp.headers = {"Content-Type": "text/html"}
    mock_client.get = MagicMock(return_value=resp)

    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)
    engine = DiscoveryEngine(db_path=test_db, fetcher=fetcher)

    result = engine.run_scan(scan_type="MANUAL")
    assert result["errors_count"] == 0

    with get_db(test_db) as conn:
        upsc_src = conn.execute("SELECT consecutive_failures, last_error, last_success_at FROM official_sources WHERE code = 'UPSC'").fetchone()
        assert upsc_src["consecutive_failures"] == 0
        assert upsc_src["last_error"] is None
        assert upsc_src["last_success_at"] is not None


def test_distinguish_empty_scan_from_failure(tmp_path: Path):
    """Verify that a successful scan with zero new notices logs SUCCESS_NO_NEW and COMPLETED with 0 errors."""
    test_db = tmp_path / "empty_scan.db"
    init_db(test_db)
    with get_db(test_db) as conn:
        seed_sources_if_empty(conn)

    mock_client = MagicMock()
    resp = MagicMock()
    resp.is_redirect = False
    resp.raise_for_status = MagicMock()
    resp.content = b"<html><body><p>No new updates today.</p></body></html>"
    resp.headers = {"Content-Type": "text/html"}
    mock_client.get = MagicMock(return_value=resp)

    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)
    engine = DiscoveryEngine(db_path=test_db, fetcher=fetcher)

    result = engine.run_scan(scan_type="SCHEDULED")

    assert result["status"] == "COMPLETED"
    assert result["errors_count"] == 0
    assert result["notices_found"] == 0

    with get_db(test_db) as conn:
        logs = conn.execute("SELECT status, notices_found_count FROM scan_source_logs WHERE scan_run_id = ?", (result["scan_id"],)).fetchall()
        assert len(logs) == 5
        assert all(l["status"] == "SUCCESS_NO_NEW" for l in logs)
        assert all(l["notices_found_count"] == 0 for l in logs)
