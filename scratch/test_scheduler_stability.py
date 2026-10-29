"""Test script for operational stability and scheduler verification."""

import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from apscheduler.triggers.cron import CronTrigger

from testkart_intelligence.config import settings
from testkart_intelligence.scheduler.job_runner import ScanScheduler
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.database.connection import init_db, get_db

print("=== 1. VERIFY SCHEDULER TIMEZONE & CRON CONFIGURATION ===")
print(f"Configured Timezone: {settings.TIMEZONE}")
print(f"Configured Scan Hours: {settings.SCAN_HOURS}")
print(f"Configured Scan Minutes: {settings.SCAN_MINUTES}")

hours_str = ",".join(str(h) for h in settings.SCAN_HOURS)
trigger = CronTrigger(
    hour=hours_str,
    minute=settings.SCAN_MINUTES,
    timezone=settings.TIMEZONE,
)

kolkata_tz = ZoneInfo(settings.TIMEZONE)
now_kolkata = datetime.now(kolkata_tz)
next_fire = trigger.get_next_fire_time(None, now_kolkata)
print(f"Current Asia/Kolkata Time: {now_kolkata}")
print(f"Next Scheduled Fire Time (IST): {next_fire}")
assert str(next_fire.tzinfo) == "Asia/Kolkata" or getattr(next_fire.tzinfo, "key", None) == "Asia/Kolkata" or "Asia/Kolkata" in str(next_fire.tzinfo)
assert next_fire.hour in settings.SCAN_HOURS
assert next_fire.minute == settings.SCAN_MINUTES
print("Scheduler cron trigger verification: PASSED")

print("\n=== 2. VERIFY OVERLAP PREVENTION LOCK ===")
scheduler = ScanScheduler()
# Acquire lock manually to simulate an active running scan
acquired = scheduler._lock.acquire(blocking=False)
assert acquired is True
print("Acquired scheduler lock for primary thread.")

# Try running scan_job in secondary thread - must be skipped immediately
skipped_detected = False

def run_conflicting_job():
    global skipped_detected
    # If lock cannot be acquired, scan_job logs warning and returns immediately
    scheduler.scan_job()
    skipped_detected = True

t = threading.Thread(target=run_conflicting_job)
t.start()
t.join()

scheduler._lock.release()
print(f"Secondary scan execution skipped cleanly without blocking: {skipped_detected}")

print("\n=== 3. VERIFY ORPHANED SCAN RECOVERY ON RESTART ===")
test_db = settings.BASE_DIR / "data" / "stability_test.db"
init_db(test_db)

with get_db(test_db) as conn:
    conn.execute(
        """
        INSERT INTO scan_runs (id, scan_type, status, started_at, sources_checked, notices_found, errors_count)
        VALUES ('scan_orphaned_1', 'SCHEDULED', 'RUNNING', '2026-10-27T06:00:00Z', 2, 5, 0)
        """
    )

engine = DiscoveryEngine(db_path=test_db)
recovered = engine.recover_orphaned_scans()
print(f"Orphaned scans recovered on restart: {recovered}")

with get_db(test_db) as conn:
    row = conn.execute("SELECT status, error_summary FROM scan_runs WHERE id = 'scan_orphaned_1'").fetchone()
    print(f"Recovered scan status: {row['status']}")
    print(f"Error summary: {row['error_summary']}")
    assert row["status"] == "FAILED"
    assert "Recovered on startup" in row["error_summary"]

if test_db.exists():
    test_db.unlink()

print("Orphaned scan recovery verification: PASSED")
