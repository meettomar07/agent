"""Targeted tests for CB-01, CB-02, and MJ-01 release remediations.

Verifies:
1. CB-01: Database connection path coercion (str vs Path) across get_connection, get_db, init_db, DiscoveryEngine.
2. CB-02: Scheduler PID identity validation and stale-lock recovery (preventing recycled PID deadlock).
3. MJ-01: Safe scheduler lock cleanup on shutdown/termination, preventing accidental deletion of another process's lock.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import psutil
import pytest

from testkart_intelligence.database.connection import get_connection, get_db, init_db
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.scheduler.job_runner import (
    ScanScheduler,
    SchedulerAlreadyRunningError,
    is_scheduler_process,
)


@pytest.fixture
def temp_db(tmp_path):
    """Provide temporary test database path as string."""
    db_file = tmp_path / "test_cb01.db"
    init_db(str(db_file))
    return str(db_file)


# ============================================================================
# CB-01: Database Connection Path Coercion Tests
# ============================================================================

def test_cb01_get_connection_with_string_path(tmp_path):
    """Verify get_connection accepts str paths and configures WAL mode without crashing on .parent."""
    db_str = str(tmp_path / "subdir" / "coercion_test.db")
    conn = get_connection(db_str)
    try:
        assert conn is not None
        row = conn.execute("PRAGMA journal_mode;").fetchone()
        assert row[0].lower() == "wal"
    finally:
        conn.close()


def test_cb01_get_db_context_manager_with_string_path(tmp_path):
    """Verify get_db context manager accepts str paths and commits transactions."""
    db_str = str(tmp_path / "tx_test.db")
    with get_db(db_str) as conn:
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, val TEXT);")
        conn.execute("INSERT INTO test_table (val) VALUES ('persisted');")

    with get_db(db_str) as conn:
        row = conn.execute("SELECT val FROM test_table WHERE id = 1;").fetchone()
        assert row["val"] == "persisted"


def test_cb01_discovery_engine_with_string_path(temp_db):
    """Verify DiscoveryEngine properly converts string db_path to Path and runs missed window detection."""
    engine = DiscoveryEngine(db_path=temp_db)
    assert isinstance(engine.db_path, Path)
    assert str(engine.db_path) == str(Path(temp_db))


# ============================================================================
# CB-02: Scheduler PID Identity & Stale-Lock Recovery Tests
# ============================================================================

def test_cb02_is_scheduler_process_identifies_scheduler_cmdline():
    """Verify is_scheduler_process identifies python scheduler processes."""
    mock_proc = MagicMock()
    mock_proc.is_running.return_value = True
    mock_proc.status.return_value = psutil.STATUS_RUNNING
    mock_proc.cmdline.return_value = ["python", "-m", "testkart_intelligence.cli", "scheduler"]
    mock_proc.name.return_value = "python.exe"

    with patch("psutil.pid_exists", return_value=True):
        with patch("psutil.Process", return_value=mock_proc):
            assert is_scheduler_process(12345) is True


def test_cb02_is_scheduler_process_rejects_unrelated_os_processes():
    """Verify is_scheduler_process returns False for unrelated system processes (preventing recycled PID deadlock)."""
    mock_proc = MagicMock()
    mock_proc.is_running.return_value = True
    mock_proc.status.return_value = psutil.STATUS_RUNNING
    mock_proc.cmdline.return_value = ["C:\\Windows\\System32\\svchost.exe", "-k", "netsvcs"]
    mock_proc.name.return_value = "svchost.exe"

    with patch("psutil.pid_exists", return_value=True):
        with patch("psutil.Process", return_value=mock_proc):
            assert is_scheduler_process(54321) is False


def test_cb02_stale_lock_recovery_with_recycled_pid(tmp_path):
    """Verify ScanScheduler.start() reclaims a lock file when the recorded PID is NOT a scheduler."""
    db_path = tmp_path / "test_sched.db"
    init_db(db_path)
    scheduler = ScanScheduler(db_path=db_path)
    ScanScheduler._active_instance = None

    # Write a foreign PID into the lock file
    foreign_pid = 77777
    with open(scheduler.lock_file, "w", encoding="utf-8") as f:
        f.write(str(foreign_pid))

    # Mock foreign PID as an unrelated running process (e.g. notepad.exe)
    mock_proc = MagicMock()
    mock_proc.is_running.return_value = True
    mock_proc.status.return_value = psutil.STATUS_RUNNING
    mock_proc.cmdline.return_value = ["notepad.exe"]
    mock_proc.name.return_value = "notepad.exe"

    with patch("psutil.pid_exists", return_value=True):
        with patch("psutil.Process", return_value=mock_proc):
            # Must NOT raise SchedulerAlreadyRunningError; must reclaim lock and start
            scheduler.start()
            try:
                assert scheduler.is_running is True
                # Lock file should now hold OUR own PID!
                with open(scheduler.lock_file, "r", encoding="utf-8") as f:
                    lock_content = f.read().strip()
                assert int(lock_content) == os.getpid()
            finally:
                scheduler.shutdown()


def test_cb02_duplicate_scheduler_prevented_with_independent_process(tmp_path):
    """Verify that an actively running independent scheduler process blocks a second scheduler."""
    db_path = tmp_path / "independent_test.db"
    init_db(db_path)
    lock_file = tmp_path / "scheduler.lock"

    # Spawn genuinely independent background python process that holds scheduler lock
    child_code = f"""
import time, os
from pathlib import Path
from testkart_intelligence.scheduler.job_runner import ScanScheduler

sched = ScanScheduler(db_path=r'{db_path}')
sched.start()
Path(r'{tmp_path / "ready.flag"}').touch()
try:
    while True:
        time.sleep(0.5)
except BaseException:
    sched.shutdown()
"""
    ready_flag = tmp_path / "ready.flag"
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-c", child_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )

    try:
        # Wait up to 10 seconds for child process to acquire lock and signal ready
        for _ in range(50):
            if ready_flag.exists() and lock_file.exists():
                break
            time.sleep(0.2)

        assert lock_file.exists(), "Child process failed to acquire scheduler lock file"
        child_pid = int(lock_file.read_text(encoding="utf-8").strip())
        assert psutil.pid_exists(child_pid)

        # Attempt to start a second scheduler in this process
        ScanScheduler._active_instance = None
        sched2 = ScanScheduler(db_path=db_path)
        with pytest.raises(SchedulerAlreadyRunningError) as exc_info:
            sched2.start()

        assert "already running in another process" in str(exc_info.value)
        assert str(child_pid) in str(exc_info.value)
    finally:
        # Gracefully stop child process
        try:
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
            proc.wait()


# ============================================================================
# MJ-01: Safe Scheduler Lock Cleanup Tests
# ============================================================================

def test_mj01_lock_cleanup_on_normal_shutdown(tmp_path):
    """Verify lock file is unlinked on scheduler.shutdown()."""
    db_path = tmp_path / "shutdown_test.db"
    init_db(db_path)
    ScanScheduler._active_instance = None
    scheduler = ScanScheduler(db_path=db_path)

    scheduler.start()
    assert scheduler.lock_file.exists()
    assert int(scheduler.lock_file.read_text(encoding="utf-8").strip()) == os.getpid()

    scheduler.shutdown()
    assert not scheduler.lock_file.exists(), "Lock file should be unlinked on shutdown"


def test_mj01_lock_cleanup_cannot_remove_another_process_lock(tmp_path):
    """CRITICAL SAFETY INVARIANT: Cleanup MUST NOT remove another active process's lock file."""
    db_path = tmp_path / "foreign_lock_test.db"
    init_db(db_path)
    ScanScheduler._active_instance = None
    scheduler = ScanScheduler(db_path=db_path)

    # Simulate another active process's lock file
    foreign_pid = 888888
    with open(scheduler.lock_file, "w", encoding="utf-8") as f:
        f.write(str(foreign_pid))

    # Calling _cleanup_lock_file() from current process (PID != 888888)
    scheduler._cleanup_lock_file()

    # The lock file MUST still exist with the foreign PID!
    assert scheduler.lock_file.exists(), "Cleanup erroneously removed a lock belonging to another process!"
    assert scheduler.lock_file.read_text(encoding="utf-8").strip() == str(foreign_pid)

    # Clean up test file manually
    scheduler.lock_file.unlink(missing_ok=True)


def test_mj01_atexit_lock_cleanup_on_normal_process_exit(tmp_path):
    """Verify that a separate subprocess running ScanScheduler unlinks its lock via atexit on normal exit."""
    db_path = tmp_path / "atexit_test.db"
    init_db(db_path)
    lock_file = tmp_path / "scheduler.lock"

    # Child starts scheduler and exits normally via sys.exit(0) WITHOUT calling shutdown()
    child_code = f"""
import sys, time
from testkart_intelligence.scheduler.job_runner import ScanScheduler

sched = ScanScheduler(db_path=r'{db_path}')
sched.start()
# Brief sleep to ensure lock file is flushed
time.sleep(0.5)
# Exit normally without calling sched.shutdown() - atexit must clean up lock!
sys.exit(0)
"""
    proc = subprocess.run(
        [sys.executable, "-c", child_code],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    # Lock file must be unlinked by atexit handler
    assert not lock_file.exists(), "Lock file was not unlinked by atexit handler upon normal process exit"


def test_mj01_subprocess_lock_cleanup_on_signal_termination(tmp_path):
    """Verify that a separate subprocess running ScanScheduler unlinks its lock file on termination signal."""
    db_path = tmp_path / "proc_term_test.db"
    init_db(db_path)
    lock_file = tmp_path / "scheduler.lock"
    ready_flag = tmp_path / "ready_term.flag"

    child_code = f"""
import time, os
from pathlib import Path
from testkart_intelligence.scheduler.job_runner import ScanScheduler

sched = ScanScheduler(db_path=r'{db_path}')
sched.start()
Path(r'{ready_flag}').touch()
while True:
    time.sleep(0.2)
"""
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-c", child_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )

    try:
        # Wait for ready
        for _ in range(50):
            if ready_flag.exists() and lock_file.exists():
                break
            time.sleep(0.2)

        assert lock_file.exists()
        child_pid = int(lock_file.read_text(encoding="utf-8").strip())
        assert psutil.pid_exists(child_pid)

        # Send termination signal (CTRL_BREAK_EVENT on Windows, SIGTERM on POSIX)
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()

        proc.wait(timeout=5)

        # Allow OS brief moment for file release
        time.sleep(0.5)
        # Lock file should be cleaned up by signal handler!
        assert not lock_file.exists(), "Lock file was not unlinked on process signal termination"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
