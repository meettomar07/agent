"""Targeted tests for MJ-04: System Diagnostic & Health Check (cli doctor).

Verifies:
1. Read-only operation: doctor NEVER modifies database, deletes lock files, or triggers scans.
2. Individual diagnostics:
   - Configuration validity (valid vs invalid timeout/retries)
   - Safety invariants (ALLOW_LIVE_PUBLISHING=False, ENABLE_EMAIL_NOTIFICATIONS=False)
   - Database connectivity, integrity, WAL mode, required 12 tables
   - Five-source whitelist & security domain allowlist
   - Scheduler lock state (UNLOCKED, ACTIVE, STALE)
   - Directory permissions (writable data and documents)
   - Timezone and next scan window calculation
3. Full CLI execution: 'python -m testkart_intelligence.cli doctor' exits 0 on valid setup.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import init_db
from testkart_intelligence.diagnostics import DiagnosticChecker, format_diagnostic_report


@pytest.fixture
def clean_diagnostic_db(tmp_path):
    """Create a fully initialized disposable test database."""
    db_file = tmp_path / "doctor_test.db"
    init_db(str(db_file))
    # Seed sources
    from testkart_intelligence.database.connection import get_db
    from testkart_intelligence.registry.service import seed_sources_if_empty
    with get_db(str(db_file)) as conn:
        seed_sources_if_empty(conn)
    return db_file


def test_doctor_read_only_guarantee(clean_diagnostic_db, tmp_path):
    """CRITICAL SAFETY TEST: Verify doctor never modifies DB records or deletes lock files."""
    checker = DiagnosticChecker(db_path=clean_diagnostic_db)
    lock_file = tmp_path / "scheduler.lock"
    lock_file.write_text("99999", encoding="utf-8")
    checker.lock_file = lock_file

    db_mtime_before = clean_diagnostic_db.stat().st_mtime
    lock_mtime_before = lock_file.stat().st_mtime

    res = checker.run_all_checks()

    # Database file mtime must not have changed
    assert clean_diagnostic_db.stat().st_mtime == db_mtime_before
    # Lock file must still exist and must NOT have been deleted or altered
    assert lock_file.exists()
    assert lock_file.read_text(encoding="utf-8") == "99999"


def test_doctor_configuration_check():
    """Verify configuration check catches valid and invalid settings."""
    checker = DiagnosticChecker()
    res = checker.check_configuration()
    assert res["passed"] is True
    assert res["status"] == "PASS"

    with patch.object(settings, "REQUEST_TIMEOUT_SECONDS", -5.0):
        fail_res = checker.check_configuration()
        assert fail_res["passed"] is False
        assert any("REQUEST_TIMEOUT_SECONDS" in d for d in fail_res["details"])


def test_doctor_safety_invariants_check():
    """Verify safety invariants flag any live publishing or email notification violations."""
    checker = DiagnosticChecker()
    res = checker.check_safety_invariants()
    assert res["passed"] is True
    assert res["status"] == "PASS"

    with patch.object(settings, "ALLOW_LIVE_PUBLISHING", True):
        fail_res = checker.check_safety_invariants()
        assert fail_res["passed"] is False
        assert any("ALLOW_LIVE_PUBLISHING" in d for d in fail_res["details"])

    with patch.object(settings, "ENABLE_EMAIL_NOTIFICATIONS", True):
        fail_res = checker.check_safety_invariants()
        assert fail_res["passed"] is False
        assert any("ENABLE_EMAIL_NOTIFICATIONS" in d for d in fail_res["details"])


def test_doctor_database_check_valid_and_missing(clean_diagnostic_db, tmp_path):
    """Verify database check passes on valid database and fails on non-existent file."""
    checker = DiagnosticChecker(db_path=clean_diagnostic_db)
    res = checker.check_database()
    assert res["passed"] is True
    assert res["status"] == "PASS"
    assert any("integrity check: OK" in d for d in res["details"])

    # Test non-existent DB
    bad_checker = DiagnosticChecker(db_path=tmp_path / "non_existent.db")
    bad_res = bad_checker.check_database()
    assert bad_res["passed"] is False
    assert "does not exist" in bad_res["details"][0]


def test_doctor_database_missing_tables(clean_diagnostic_db):
    """Verify database check detects if required tables are missing."""
    import sqlite3
    conn = sqlite3.connect(clean_diagnostic_db)
    conn.execute("DROP TABLE publishing_jobs;")
    conn.close()

    checker = DiagnosticChecker(db_path=clean_diagnostic_db)
    res = checker.check_database()
    assert res["passed"] is False
    assert any("Missing required tables" in d and "publishing_jobs" in d for d in res["details"])


def test_doctor_sources_whitelist_check(clean_diagnostic_db):
    """Verify sources whitelist check passes on the authorized 5 sources."""
    checker = DiagnosticChecker(db_path=clean_diagnostic_db)
    res = checker.check_sources_whitelist()
    assert res["passed"] is True
    assert any("Authorized 5 sources active" in d for d in res["details"])


def test_doctor_scheduler_lock_states(tmp_path):
    """Verify lock diagnostics for UNLOCKED, ACTIVE, and STALE states without modifying disk."""
    checker = DiagnosticChecker(db_path=tmp_path / "dummy.db")
    lock_file = tmp_path / "scheduler.lock"
    checker.lock_file = lock_file

    # 1. UNLOCKED
    lock_file.unlink(missing_ok=True)
    res = checker.check_scheduler_lock()
    assert res["lock_status"] == "UNLOCKED"

    # 2. ACTIVE
    lock_file.write_text("12345", encoding="utf-8")
    with patch("testkart_intelligence.diagnostics.is_scheduler_process", return_value=True):
        res = checker.check_scheduler_lock()
        assert res["lock_status"] == "ACTIVE"

    # 3. STALE
    with patch("testkart_intelligence.diagnostics.is_scheduler_process", return_value=False):
        res = checker.check_scheduler_lock()
        assert res["lock_status"] == "STALE"

    # Lock file must still exist (read-only verification)
    assert lock_file.exists()
    lock_file.unlink(missing_ok=True)


def test_doctor_directory_permissions(clean_diagnostic_db):
    """Verify directory check passes on accessible data directories."""
    checker = DiagnosticChecker(db_path=clean_diagnostic_db)
    res = checker.check_directory_permissions()
    assert res["passed"] is True
    assert res["status"] == "PASS"


def test_doctor_schedule_timing():
    """Verify schedule timing calculation calculates local time and next scan window."""
    checker = DiagnosticChecker()
    res = checker.check_schedule_timing()
    assert res["passed"] is True
    assert any("Next scheduled window" in d for d in res["details"])


def test_doctor_cli_command_execution(clean_diagnostic_db):
    """Verify 'python -m testkart_intelligence.cli doctor --db <path>' runs end-to-end and exits 0."""
    res = subprocess.run(
        [sys.executable, "-m", "testkart_intelligence.cli", "doctor", "--db", str(clean_diagnostic_db)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"doctor CLI failed: {res.stderr}"
    assert "Overall Result: ALL DIAGNOSTIC CHECKS PASSED" in res.stdout
    assert "1. Configuration Validity" in res.stdout
    assert "2. Safety Invariants & Guardrails" in res.stdout
    assert "3. Database Connectivity & Integrity" in res.stdout
    assert "4. Five-Source Whitelist & Allowlist" in res.stdout
    assert "5. Scheduler Lock State" in res.stdout
    assert "6. Directory & Storage Permissions" in res.stdout
    assert "7. Timezone & Schedule Timing" in res.stdout
