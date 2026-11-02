"""Real-World 30-Day Supervised Pilot Initialization Script.

Performs:
1. Creation and schema verification of data/real_world_pilot_30day.db.
2. Verification of source registry (5 enabled: UPSC, SSC, NTA, UPPSC, TNPSC).
3. Recording of exact Asia/Kolkata initialization timestamp in system_metadata.
4. Setup of .env configuration targeting data/real_world_pilot_30day.db.
5. Verification of safety invariants (ALLOW_LIVE_PUBLISHING = False, ENABLE_EMAIL_NOTIFICATIONS = False).
6. Preservation audit of data/testkart.db and data/operational_pilot_30day.db.
7. Testing scheduler process initialization and cross-process lock (scheduler.lock).
8. Execution of the first baseline live scan across the 5 official portals with detailed source-level logs.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import sqlite3

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from testkart_intelligence.config import Settings
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import SourceRegistryService, seed_sources_if_empty
from testkart_intelligence.publishing.guard import assert_live_publishing_disabled
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.scheduler.job_runner import ScanScheduler, SchedulerAlreadyRunningError


def main():
    tz = ZoneInfo("Asia/Kolkata")
    init_time = datetime.now(tz)
    init_time_iso = init_time.isoformat()
    first_window = datetime(2026, 11, 2, 18, 0, 0, tzinfo=tz)
    end_date = first_window + timedelta(days=30)
    end_date_iso = end_date.isoformat()

    print("==========================================================================")
    print(" Testkart Government Exam Intelligence - Real-World Pilot Initialization")
    print(f" Current Timestamp (Asia/Kolkata): {init_time_iso}")
    print(f" First Scheduled Window:           {first_window.isoformat()}")
    print(f" Intended Pilot Completion (Day 30): {end_date_iso}")
    print("==========================================================================")

    # 1. Establish dedicated real-world pilot database
    pilot_db_path = ROOT_DIR / "data" / "real_world_pilot_30day.db"
    print(f"\n[Step 1] Initializing clean dedicated pilot database: {pilot_db_path.name}")
    init_db(pilot_db_path)

    with get_db(pilot_db_path) as conn:
        seeded = seed_sources_if_empty(conn)
        print(f"  - Initialized schema and seeded {seeded} official sources.")

        # Verify initial clean state
        counts = {
            "scan_runs": conn.execute("SELECT count(*) as c FROM scan_runs").fetchone()["c"],
            "canonical_notices": conn.execute("SELECT count(*) as c FROM canonical_notices").fetchone()["c"],
            "notice_versions": conn.execute("SELECT count(*) as c FROM notice_versions").fetchone()["c"],
            "blog_articles": conn.execute("SELECT count(*) as c FROM blog_articles").fetchone()["c"],
            "approval_records": conn.execute("SELECT count(*) as c FROM approval_records").fetchone()["c"],
            "publishing_jobs": conn.execute("SELECT count(*) as c FROM publishing_jobs").fetchone()["c"],
            "official_sources": conn.execute("SELECT count(*) as c FROM official_sources").fetchone()["c"],
            "enabled_sources": conn.execute("SELECT count(*) as c FROM official_sources WHERE enabled = 1").fetchone()["c"],
        }
        print("  - Initial database counts:")
        for tbl, cnt in counts.items():
            print(f"    * {tbl:<20}: {cnt}")

        assert counts["scan_runs"] == 0, "Dedicated pilot DB must start with 0 scan runs"
        assert counts["canonical_notices"] == 0, "Dedicated pilot DB must start with 0 notices"
        assert counts["blog_articles"] == 0, "Dedicated pilot DB must start with 0 articles"
        assert counts["approval_records"] == 0, "Dedicated pilot DB must start with 0 approvals"
        assert counts["publishing_jobs"] == 0, "Dedicated pilot DB must start with 0 publications"
        assert counts["enabled_sources"] == 5, "Exactly 5 official sources must be enabled"

        # Verify the 5 enabled sources
        enabled_rows = conn.execute(
            "SELECT code, name, official_domain FROM official_sources WHERE enabled = 1 ORDER BY code"
        ).fetchall()
        enabled_codes = [r["code"] for r in enabled_rows]
        print(f"  - Enabled bodies: {', '.join(enabled_codes)}")
        assert set(enabled_codes) == {"NTA", "SSC", "TNPSC", "UPSC", "UPPSC"}, f"Unexpected enabled sources: {enabled_codes}"

    # 2. Record pilot initialization metadata in system_metadata
    print("\n[Step 2] Recording pilot initialization metadata...")
    metadata_entries = [
        ("pilot_initialized_at", init_time_iso),
        ("pilot_start_time", init_time_iso),
        ("pilot_first_window", first_window.isoformat()),
        ("pilot_intended_end_date", end_date_iso),
        ("pilot_target_calendar_days", "30"),
        ("pilot_target_scheduled_windows", "60"),
        ("pilot_mode", "REAL_WORLD_SUPERVISED_PILOT"),
        ("lead_reviewer_email", "meettomar07@gmail.com"),
        ("git_commit", "cd7efab"),
        ("enabled_sources", "UPSC,SSC,NTA,UPPSC,TNPSC"),
        ("allow_live_publishing", "False"),
        ("enable_email_notifications", "False"),
        ("database_path", str(pilot_db_path)),
    ]

    with get_db(pilot_db_path) as conn:
        for k, v in metadata_entries:
            conn.execute(
                """
                INSERT INTO system_metadata (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (k, v, init_time_iso),
            )
        print(f"  - Successfully recorded {len(metadata_entries)} pilot metadata records.")

    # 3. Write .env configuration to route default settings to pilot database
    print("\n[Step 3] Configuring environment settings for pilot operation...")
    env_path = ROOT_DIR / ".env"
    env_content = (
        f"# Testkart Real-World 30-Day Supervised Pilot Configuration\n"
        f"TESTKART_DATABASE_PATH=data/real_world_pilot_30day.db\n"
        f"TESTKART_TIMEZONE=Asia/Kolkata\n"
        f"TESTKART_SCAN_HOURS=[6, 18]\n"
        f"TESTKART_SCAN_MINUTES=0\n"
        f"TESTKART_ALLOW_LIVE_PUBLISHING=False\n"
        f"TESTKART_ENABLE_EMAIL_NOTIFICATIONS=False\n"
        f"TESTKART_OWNER_EMAIL=meettomar07@gmail.com\n"
        f"TESTKART_SERVER_HOST=127.0.0.1\n"
        f"TESTKART_SERVER_PORT=8000\n"
    )
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    print(f"  - Created {env_path.name} referencing {pilot_db_path.name}.")

    # Re-instantiate settings to verify
    settings = Settings()
    print("  - Verifying settings loaded from .env:")
    print(f"    * DATABASE_PATH:             {settings.DATABASE_PATH}")
    print(f"    * TIMEZONE:                  {settings.TIMEZONE}")
    print(f"    * SCAN_HOURS:                {settings.SCAN_HOURS}")
    print(f"    * ALLOW_LIVE_PUBLISHING:     {settings.ALLOW_LIVE_PUBLISHING}")
    print(f"    * ENABLE_EMAIL_NOTIFICATIONS: {settings.ENABLE_EMAIL_NOTIFICATIONS}")
    assert not settings.ALLOW_LIVE_PUBLISHING, "ALLOW_LIVE_PUBLISHING must remain False"
    assert not settings.ENABLE_EMAIL_NOTIFICATIONS, "ENABLE_EMAIL_NOTIFICATIONS must remain False"
    assert_live_publishing_disabled()
    print("  - Hard safety invariant assertions PASSED.")

    # 4. Verify preservation of existing database files
    print("\n[Step 4] Verifying preservation of existing databases and evaluation datasets...")
    db_testkart = ROOT_DIR / "data" / "testkart.db"
    db_sim_pilot = ROOT_DIR / "data" / "operational_pilot_30day.db"
    assert db_testkart.exists(), "data/testkart.db must exist and be preserved"
    assert db_sim_pilot.exists(), "data/operational_pilot_30day.db must exist and be preserved"

    with sqlite3.connect(str(db_testkart)) as conn:
        c_not = conn.execute("SELECT count(*) FROM canonical_notices").fetchone()[0]
        print(f"  - Verified data/testkart.db: {c_not} canonical notices intact.")

    with sqlite3.connect(str(db_sim_pilot)) as conn:
        c_runs = conn.execute("SELECT count(*) FROM scan_runs").fetchone()[0]
        print(f"  - Verified data/operational_pilot_30day.db: {c_runs} scan runs intact.")

    # 5. Verify Scheduler Initialization and Cross-Process Lock
    print("\n[Step 5] Verifying scheduler initialization and cross-process locking...")
    scheduler = ScanScheduler(db_path=pilot_db_path)
    scheduler.start()
    assert scheduler.is_running is True
    sched_status = scheduler.get_status()
    print(f"  - Scheduler started successfully:")
    print(f"    * Running:         {sched_status['running']}")
    print(f"    * Timezone:        {sched_status['timezone']}")
    print(f"    * Hours:           {sched_status['scan_hours']}")
    print(f"    * Next Run Time:   {sched_status['next_run_time']}")
    print(f"    * Lock File Exists: {scheduler.lock_file.exists()} (PID: {os.getpid()})")
    assert scheduler.lock_file.exists(), "scheduler.lock must be created on start"

    # Test that duplicate start raises SchedulerAlreadyRunningError
    sched_dup = ScanScheduler(db_path=pilot_db_path)
    try:
        sched_dup.start()
        raise AssertionError("Duplicate scheduler start should have been blocked!")
    except SchedulerAlreadyRunningError as e:
        print(f"  - Duplicate scheduler start blocked as expected: {e}")

    # Shutdown test instance
    scheduler.shutdown()
    assert not scheduler.is_running
    assert not scheduler.lock_file.exists(), "scheduler.lock must be deleted on shutdown"
    print("  - Scheduler shutdown and lock release verified.")

    # 6. Execute and record the First Baseline Live Discovery Scan
    print("\n[Step 6] Executing and recording first actual pre-launch live discovery scan...")
    engine = DiscoveryEngine(db_path=pilot_db_path)
    scan_result = engine.run_scan(scan_type="MANUAL")

    print(f"  - Scan ID:         {scan_result['scan_id']}")
    print(f"  - Overall Status:  {scan_result['status']}")
    print(f"  - Sources Checked: {scan_result['sources_checked']}")
    print(f"  - Notices Found:   {scan_result['notices_found']}")
    print(f"  - New Notices:     {scan_result['new_notices']}")
    print(f"  - Errors Logged:   {scan_result['errors_count']}")
    if scan_result["error_summary"]:
        for err in scan_result["error_summary"]:
            print(f"    * Warning/Error: {err}")

    # Inspect source-level logs from database
    with get_db(pilot_db_path) as conn:
        source_logs = conn.execute(
            """
            SELECT s.code, s.name, ssl.status, ssl.notices_found_count, ssl.response_time_ms, ssl.error_message, ssl.checked_at
            FROM scan_source_logs ssl
            JOIN official_sources s ON ssl.source_id = s.id
            WHERE ssl.scan_run_id = ?
            ORDER BY s.code
            """,
            (scan_result["scan_id"],),
        ).fetchall()

        print("\n  - Source-Level Execution Telemetry:")
        print(f"    {'CODE':<8} {'STATUS':<16} {'NOTICES':<10} {'LATENCY (ms)':<14} {'CHECKED AT (UTC)'}")
        print("    " + "-" * 75)
        for row in source_logs:
            print(f"    {row['code']:<8} {row['status']:<16} {row['notices_found_count']:<10} {row['response_time_ms']:<14} {row['checked_at']}")

        # Summary of canonical notices discovered
        notices_count = conn.execute("SELECT count(*) as c FROM canonical_notices").fetchone()["c"]
        print(f"\n  - Total Canonical Notices in Pilot Database: {notices_count}")

    print("\n==========================================================================")
    print(" Phase 2 Pilot Initialization Complete.")
    print(" Dedicated Database: data/real_world_pilot_30day.db")
    print(f" Official 30-Day Operational Window: {first_window.isoformat()} to {end_date_iso}")
    print("==========================================================================")


if __name__ == "__main__":
    main()
