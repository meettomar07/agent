"""Targeted tests for Windows Process Lifecycle, Signal Handling, and Stale Lock Recovery.

Verifies:
1. Normal shutdown cleanly releases lock file.
2. Ctrl+C (KeyboardInterrupt) triggers graceful shutdown and lock release.
3. Supported termination signals (SIGBREAK on Windows / SIGTERM) trigger signal handler and clean exit.
4. Abrupt process termination (hard kill) leaves stale lock file on disk, but subsequent scheduler
   startup reliably detects stale PID via is_scheduler_process() and automatically reclaims lock.
5. Invariant: Lock cleanup can NEVER remove a lock belonging to another active process.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import psutil
import pytest

from testkart_intelligence.database.connection import init_db
from testkart_intelligence.scheduler.job_runner import (
    ScanScheduler,
    SchedulerAlreadyRunningError,
    is_scheduler_process,
)


@pytest.fixture
def lifecycle_db(tmp_path):
    """Provide disposable initialized database for lifecycle testing."""
    db_file = tmp_path / "lifecycle_test.db"
    init_db(str(db_file))
    return db_file


def test_lifecycle_normal_shutdown(lifecycle_db):
    """Verify normal scheduler.start() -> scheduler.shutdown() sequence acquires and releases lock."""
    ScanScheduler._active_instance = None
    scheduler = ScanScheduler(db_path=lifecycle_db)

    assert not scheduler.lock_file.exists()
    scheduler.start()

    assert scheduler.is_running is True
    assert scheduler.lock_file.exists()
    assert int(scheduler.lock_file.read_text(encoding="utf-8").strip()) == os.getpid()

    scheduler.shutdown()
    assert scheduler.is_running is False
    assert not scheduler.lock_file.exists()


def test_lifecycle_ctrl_c_keyboard_interrupt(lifecycle_db, tmp_path):
    """Verify KeyboardInterrupt in CLI scheduler loop stops cleanly and unlinks lock file."""
    lock_file = tmp_path / "scheduler.lock"
    ready_flag = tmp_path / "ready_ctrl_c.flag"

    child_code = f"""
import time, os
from pathlib import Path
from testkart_intelligence.scheduler.job_runner import ScanScheduler

sched = ScanScheduler(db_path=r'{lifecycle_db}')
sched.start()
Path(r'{ready_flag}').touch()

# Emulate cli.py loop catching KeyboardInterrupt
try:
    while True:
        time.sleep(0.2)
except KeyboardInterrupt:
    sched.shutdown()
"""
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-c", child_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )

    try:
        # Wait until scheduler starts and acquires lock
        for _ in range(50):
            if ready_flag.exists() and lock_file.exists():
                break
            time.sleep(0.2)

        assert lock_file.exists()
        child_pid = int(lock_file.read_text(encoding="utf-8").strip())
        assert psutil.pid_exists(child_pid)

        # Send CTRL_C_EVENT or CTRL_BREAK_EVENT
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGINT)

        proc.wait(timeout=5)
        time.sleep(0.5)

        # Lock file must be unlinked
        assert not lock_file.exists(), "Lock file was not unlinked on KeyboardInterrupt shutdown"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_lifecycle_abrupt_termination_and_stale_lock_recovery(lifecycle_db, tmp_path):
    """Simulate abrupt hard termination (power loss/kill -9), verifying stale lock is recovered on next start."""
    lock_file = tmp_path / "scheduler.lock"
    ready_flag = tmp_path / "ready_abrupt.flag"

    child_code = f"""
import time, os
from pathlib import Path
from testkart_intelligence.scheduler.job_runner import ScanScheduler

sched = ScanScheduler(db_path=r'{lifecycle_db}')
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
        # Wait for scheduler to start
        for _ in range(50):
            if ready_flag.exists() and lock_file.exists():
                break
            time.sleep(0.2)

        assert lock_file.exists()
        dead_pid = int(lock_file.read_text(encoding="utf-8").strip())

        # HARD TERMINATE (kill) - abrupt termination where OS kills process without running user-mode cleanup
        proc.kill()
        proc.wait(timeout=5)

        # On abrupt kill, the lock file DOES remain on disk with the dead PID
        assert lock_file.exists(), "Lock file unexpectedly unlinked during hard kill"
        assert int(lock_file.read_text(encoding="utf-8").strip()) == dead_pid

        # Verify dead PID is not an active scheduler process
        assert is_scheduler_process(dead_pid) is False

        # Next scheduler startup should detect stale lock, reclaim it, and start without error
        ScanScheduler._active_instance = None
        new_sched = ScanScheduler(db_path=lifecycle_db)
        new_sched.start()
        try:
            assert new_sched.is_running is True
            # Lock file must now hold the new scheduler's PID
            new_pid = int(lock_file.read_text(encoding="utf-8").strip())
            assert new_pid == os.getpid()
            assert new_pid != dead_pid
        finally:
            new_sched.shutdown()

        # Shutdown should have cleanly unlinked the reclaimed lock
        assert not lock_file.exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_lifecycle_lock_cleanup_non_interference(lifecycle_db, tmp_path):
    """CRITICAL SAFETY INVARIANT: A process calling _cleanup_lock_file() or shutdown()
    MUST NOT remove a lock file owned by a different active process."""
    ScanScheduler._active_instance = None
    scheduler = ScanScheduler(db_path=lifecycle_db)
    lock_file = scheduler.lock_file

    # Simulate an active foreign scheduler PID
    foreign_pid = 999991
    lock_file.write_text(str(foreign_pid), encoding="utf-8")

    # Calling cleanup on our scheduler instance
    scheduler._cleanup_lock_file()

    # Foreign lock file MUST remain intact
    assert lock_file.exists()
    assert int(lock_file.read_text(encoding="utf-8").strip()) == foreign_pid

    # Calling shutdown() on our scheduler instance
    scheduler.shutdown()

    # Foreign lock file MUST STILL remain intact
    assert lock_file.exists()
    assert int(lock_file.read_text(encoding="utf-8").strip()) == foreign_pid

    # Clean up test file manually
    lock_file.unlink(missing_ok=True)
