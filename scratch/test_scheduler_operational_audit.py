import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

from testkart_intelligence.scheduler.job_runner import ScanScheduler, SchedulerAlreadyRunningError
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.config import settings

db_path = Path("data/test_scheduler_audit.db")
if db_path.exists():
    db_path.unlink()

init_db(db_path)

print("=== 1. SCHEDULER STARTUP AND SHUTDOWN VERIFICATION ===")
sched = ScanScheduler(db_path=db_path)
assert not sched.is_running, "Scheduler should not be running prior to start()"

sched.start()
assert sched.is_running, "Scheduler should be running after start()"
status = sched.get_status()
print(f"Scheduler Status: running={status['running']}, timezone={status['timezone']}")
print(f"Scan Hours: {status['scan_hours']} (IST), Next Run: {status['next_run_time']}")
assert status["running"] is True
assert status["timezone"] == "Asia/Kolkata"
assert status["scan_hours"] == [6, 18]
assert status["next_run_time"] is not None

print("\n=== 2. DUPLICATE INSTANCE PREVENTION VERIFICATION ===")
sched2 = ScanScheduler(db_path=db_path)
duplicate_prevented = False
try:
    sched2.start()
except SchedulerAlreadyRunningError as e:
    duplicate_prevented = True
    print(f"Successfully caught expected SchedulerAlreadyRunningError: {e}")

assert duplicate_prevented, "Duplicate scheduler startup was NOT prevented!"

# Shutdown first instance
sched.shutdown()
assert not sched.is_running, "Scheduler should not be running after shutdown()"
print("Instance 1 cleanly shut down.")

print("\n=== 3. OVERLAPPING SCAN PROTECTION VERIFICATION ===")
sched3 = ScanScheduler(db_path=db_path)
# Acquire internal scan lock to simulate an ongoing long-running scan
acquired = sched3._lock.acquire(blocking=False)
assert acquired, "Should acquire lock"

# Call scan_job while lock is held
t0 = time.time()
sched3.scan_job() # Should immediately return and skip scan
elapsed = time.time() - t0
sched3._lock.release()
print(f"Overlapping scan skipped immediately (elapsed: {elapsed:.4f}s)")
assert elapsed < 0.5, "Scan job should have skipped immediately without blocking"

print("\n=== 4. ORPHANED / FAILED SCAN RECOVERY VERIFICATION ===")
with get_db(db_path) as conn:
    conn.execute(
        """
        INSERT INTO scan_runs (
            id, scan_type, started_at, completed_at, status, sources_checked, notices_found, errors_count
        ) VALUES (
            'scan_orphaned_01', 'SCHEDULED', '2026-10-29T06:00:00Z', NULL, 'RUNNING', 5, 0, 0
        )
        """
    )

recovered_count = sched3.engine.recover_orphaned_scans()
print(f"Recovered orphaned scans count: {recovered_count}")
assert recovered_count == 1, f"Expected 1 recovered scan, got {recovered_count}"

with get_db(db_path) as conn:
    row = conn.execute("SELECT status, error_summary, completed_at FROM scan_runs WHERE id = 'scan_orphaned_01'").fetchone()
    print(f"Orphaned scan new status: {row['status']}")
    print(f"Error summary: {row['error_summary']}")
    assert row["status"] == "FAILED"
    assert "Recovered on startup" in row["error_summary"]
    assert row["completed_at"] is not None

print("\n=======================================================")
print("ALL 4 OPERATIONAL SCHEDULER TESTS VERIFIED SUCCESSFULLY!")
print("=======================================================")
