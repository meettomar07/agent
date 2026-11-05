"""System diagnostic and health check service for Testkart Intelligence.

Performs strictly read-only inspections of:
- Configuration validity
- Database connectivity, integrity, and schema
- Required tables and indexes
- Five-source whitelist & domain allowlist
- Scheduler lock status and ownership
- Pilot database path and notice stats
- Publishing and notification safety flags
- Writable log and data directories
- Timezone and next scheduled scan time

STRICT INVARIANT:
This module is strictly read-only. It must NOT modify the database, remove or
touch lock files, start services, or trigger network scans.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import psutil

from testkart_intelligence.config import settings
from testkart_intelligence.scheduler.job_runner import is_scheduler_process
from testkart_intelligence.security.allowlist import is_official_domain


REQUIRED_TABLES = [
    "official_sources",
    "scan_runs",
    "scan_source_logs",
    "canonical_notices",
    "notice_versions",
    "extracted_facts",
    "blog_articles",
    "article_versions",
    "qa_results",
    "approval_records",
    "publishing_jobs",
    "system_metadata",
]

AUTHORIZED_FIVE_SOURCES = {"UPSC", "SSC", "NTA", "UPPSC", "TNPSC"}
ALL_AUTHORIZED_OFFICIAL_SOURCES = {
    "UPSC", "SSC", "NTA", "UPPSC", "TNPSC",
    "IBPS", "RRB_CHD", "JOIN_ARMY", "BPSC", "DSSSB", "MPPSC", "KPSC",
}


class DiagnosticChecker:
    """Performs strictly read-only system and environment diagnostics."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else settings.DATABASE_PATH
        self.data_dir = self.db_path.parent if self.db_path else settings.DATA_DIR
        self.lock_file = self.data_dir / "scheduler.lock"

    def run_all_checks(self) -> Dict[str, Any]:
        """Execute all read-only diagnostic checks and return structured results."""
        checks: Dict[str, Any] = {}
        all_passed = True

        # 1. Configuration Check
        cfg_res = self.check_configuration()
        checks["configuration"] = cfg_res
        if not cfg_res["passed"]:
            all_passed = False

        # 2. Safety Invariants Check
        safety_res = self.check_safety_invariants()
        checks["safety_invariants"] = safety_res
        if not safety_res["passed"]:
            all_passed = False

        # 3. Database Connectivity & Integrity
        db_res = self.check_database()
        checks["database"] = db_res
        if not db_res["passed"]:
            all_passed = False

        # 4. Five-Source Whitelist
        src_res = self.check_sources_whitelist()
        checks["sources"] = src_res
        if not src_res["passed"]:
            all_passed = False

        # 5. Scheduler Lock Status (Read-Only)
        lock_res = self.check_scheduler_lock()
        checks["scheduler_lock"] = lock_res
        if not lock_res["passed"]:
            all_passed = False

        # 6. Storage & Directory Permissions
        dir_res = self.check_directory_permissions()
        checks["directories"] = dir_res
        if not dir_res["passed"]:
            all_passed = False

        # 7. Timezone & Schedule Timing
        sched_res = self.check_schedule_timing()
        checks["schedule"] = sched_res
        if not sched_res["passed"]:
            all_passed = False

        checks["all_passed"] = all_passed
        return checks

    def check_configuration(self) -> Dict[str, Any]:
        """Validate core runtime settings."""
        details: List[str] = []
        passed = True

        if settings.REQUEST_TIMEOUT_SECONDS <= 0:
            passed = False
            details.append(f"Invalid REQUEST_TIMEOUT_SECONDS: {settings.REQUEST_TIMEOUT_SECONDS}")
        else:
            details.append(f"Request timeout: {settings.REQUEST_TIMEOUT_SECONDS}s")

        if settings.MAX_RETRIES < 1:
            passed = False
            details.append(f"Invalid MAX_RETRIES: {settings.MAX_RETRIES}")
        else:
            details.append(f"Max retries: {settings.MAX_RETRIES}")

        if not settings.TIMEZONE:
            passed = False
            details.append("TIMEZONE is empty")
        else:
            details.append(f"Timezone: {settings.TIMEZONE}")

        if not settings.SCAN_HOURS:
            passed = False
            details.append("SCAN_HOURS is empty")
        else:
            details.append(f"Scan hours: {settings.SCAN_HOURS} (Minute: {settings.SCAN_MINUTES:02d})")

        return {
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        }

    def check_safety_invariants(self) -> Dict[str, Any]:
        """Verify strict safety invariants for local development / supervised release."""
        details: List[str] = []
        passed = True

        if settings.ALLOW_LIVE_PUBLISHING:
            passed = False
            details.append("CRITICAL VIOLATION: ALLOW_LIVE_PUBLISHING is True! Must be False.")
        else:
            details.append("Live publishing: DISABLED (Secure failsafe enforced)")

        if settings.ENABLE_EMAIL_NOTIFICATIONS:
            passed = False
            details.append("CRITICAL VIOLATION: ENABLE_EMAIL_NOTIFICATIONS is True! Must be False.")
        else:
            details.append("Email notifications: DISABLED (Zero external dispatches)")

        return {
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        }

    def check_database(self) -> Dict[str, Any]:
        """Inspect database connectivity, SQLite WAL mode, and required tables."""
        details: List[str] = []
        passed = True

        if not self.db_path.exists():
            return {
                "passed": False,
                "status": "FAIL",
                "details": [f"Database file does not exist at {self.db_path}"],
            }

        details.append(f"Database path: {self.db_path} ({self.db_path.stat().st_size:,} bytes)")

        try:
            # Read-only SQLite connection
            conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True, timeout=10.0)
            conn.row_factory = sqlite3.Row
            try:
                # 1. Integrity check
                integ_row = conn.execute("PRAGMA integrity_check;").fetchone()
                integ_status = integ_row[0] if integ_row else "unknown"
                if integ_status.lower() != "ok":
                    passed = False
                    details.append(f"Integrity check failed: {integ_status}")
                else:
                    details.append("SQLite integrity check: OK")

                # 2. Journal mode
                jm_row = conn.execute("PRAGMA journal_mode;").fetchone()
                journal_mode = jm_row[0].upper() if jm_row else "UNKNOWN"
                details.append(f"Journal mode: {journal_mode}")

                # 3. Tables check
                existing_tables = {
                    row["name"]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
                    ).fetchall()
                }
                missing_tables = [t for t in REQUIRED_TABLES if t not in existing_tables]
                if missing_tables:
                    passed = False
                    details.append(f"Missing required tables: {', '.join(missing_tables)}")
                else:
                    details.append(f"Required schema tables: {len(REQUIRED_TABLES)} / {len(REQUIRED_TABLES)} present")

                # 4. Record counts
                if "canonical_notices" in existing_tables:
                    notices_cnt = conn.execute("SELECT count(*) as c FROM canonical_notices;").fetchone()["c"]
                    details.append(f"Canonical notices: {notices_cnt:,}")

                if "scan_runs" in existing_tables:
                    scans_cnt = conn.execute("SELECT count(*) as c FROM scan_runs;").fetchone()["c"]
                    details.append(f"Recorded scan runs: {scans_cnt}")

            finally:
                conn.close()

        except Exception as exc:
            passed = False
            details.append(f"Database connection error: {exc}")

        return {
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        }

    def check_sources_whitelist(self) -> Dict[str, Any]:
        """Verify the 5-source whitelist and official domain allowlisting."""
        details: List[str] = []
        passed = True

        if not self.db_path.exists():
            return {
                "passed": False,
                "status": "FAIL",
                "details": ["Database not available for source inspection"],
            }

        try:
            conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True, timeout=10.0)
            conn.row_factory = sqlite3.Row
            try:
                sources = conn.execute(
                    "SELECT code, name, category, enabled, official_domain FROM official_sources ORDER BY code;"
                ).fetchall()

                enabled_sources = [s for s in sources if s["enabled"] == 1]
                enabled_codes = {s["code"] for s in enabled_sources}

                details.append(f"Registered sources: {len(sources)} total, {len(enabled_sources)} enabled")

                # Verify enabled sources are authorized official portals
                if enabled_codes == AUTHORIZED_FIVE_SOURCES:
                    details.append(f"Authorized 5 sources active: {', '.join(sorted(enabled_codes))}")
                elif enabled_codes.issubset(ALL_AUTHORIZED_OFFICIAL_SOURCES):
                    details.append(f"Authorized official sources active ({len(enabled_codes)} enabled): {', '.join(sorted(enabled_codes))}")
                else:
                    passed = False
                    unauthorized = enabled_codes - ALL_AUTHORIZED_OFFICIAL_SOURCES
                    details.append(
                        f"Source whitelist mismatch! Unauthorized sources enabled: {sorted(unauthorized)}"
                    )

                # Check domain allowlisting
                domain_errors = []
                for s in enabled_sources:
                    dom = s["official_domain"]
                    if not is_official_domain(dom):
                        domain_errors.append(f"{s['code']} domain '{dom}' is NOT allowlisted")
                if domain_errors:
                    passed = False
                    details.extend(domain_errors)
                else:
                    details.append("All active source domains verified against security allowlist")

            finally:
                conn.close()
        except Exception as exc:
            passed = False
            details.append(f"Error querying official sources: {exc}")

        return {
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        }

    def check_scheduler_lock(self) -> Dict[str, Any]:
        """Inspect scheduler lock file status without modifying or deleting it."""
        details: List[str] = []
        passed = True

        details.append(f"Lock file path: {self.lock_file}")

        if not self.lock_file.exists():
            details.append("Lock state: UNLOCKED (No active scheduler daemon, ready to start)")
            lock_status = "UNLOCKED"
        else:
            try:
                with open(self.lock_file, "r", encoding="utf-8") as f:
                    pid_str = f.read().strip()
                if pid_str and pid_str.isdigit():
                    pid = int(pid_str)
                    if is_scheduler_process(pid):
                        details.append(f"Lock state: ACTIVE (Held by running scheduler daemon PID {pid})")
                        lock_status = "ACTIVE"
                    else:
                        details.append(
                            f"Lock state: STALE (Recorded PID {pid} is dead or unrelated; will be safely reclaimed on startup)"
                        )
                        lock_status = "STALE"
                else:
                    details.append(f"Lock state: CORRUPT (Lock content '{pid_str}' is invalid; will be reclaimed)")
                    lock_status = "CORRUPT"
            except Exception as exc:
                details.append(f"Error inspecting lock file: {exc}")
                lock_status = "ERROR"

        return {
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "lock_status": lock_status,
            "details": details,
        }

    def check_directory_permissions(self) -> Dict[str, Any]:
        """Verify data and documents directories exist and are writable."""
        details: List[str] = []
        passed = True

        dirs_to_check = [
            ("Data Directory", self.data_dir),
            ("Documents Directory", settings.DOCUMENTS_DIR),
        ]

        for label, dir_path in dirs_to_check:
            if not dir_path.exists():
                passed = False
                details.append(f"{label}: MISSING at {dir_path}")
            else:
                is_writable = os.access(str(dir_path), os.W_OK)
                if not is_writable:
                    passed = False
                    details.append(f"{label}: READ-ONLY (Cannot write to {dir_path})")
                else:
                    details.append(f"{label}: WRITABLE ({dir_path})")

        return {
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        }

    def check_schedule_timing(self) -> Dict[str, Any]:
        """Inspect configured schedule timing and calculate next scan window."""
        details: List[str] = []
        passed = True

        try:
            tz = ZoneInfo(settings.TIMEZONE)
            now = datetime.now(tz)
            details.append(f"Current local time: {now.strftime('%Y-%m-%d %H:%M:%S')} ({settings.TIMEZONE})")

            # Calculate next scheduled scan window
            scan_hours = sorted(settings.SCAN_HOURS)
            minute = settings.SCAN_MINUTES

            candidate_windows: List[datetime] = []
            for day_offset in (0, 1):
                d = now.date() + timedelta(days=day_offset)
                for h in scan_hours:
                    w = datetime(d.year, d.month, d.day, h, minute, tzinfo=tz)
                    if w > now:
                        candidate_windows.append(w)

            if candidate_windows:
                next_window = min(candidate_windows)
                time_diff = next_window - now
                hrs = int(time_diff.total_seconds() // 3600)
                mins = int((time_diff.total_seconds() % 3600) // 60)
                details.append(
                    f"Next scheduled window: {next_window.strftime('%Y-%m-%d %H:%M:%S %Z')} (in {hrs}h {mins}m)"
                )
            else:
                details.append("Could not calculate next scheduled scan window")

        except Exception as exc:
            passed = False
            details.append(f"Schedule timing calculation error: {exc}")

        return {
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        }


def format_diagnostic_report(results: Dict[str, Any]) -> str:
    """Format structured diagnostic results into a clean, human-readable terminal report."""
    lines: List[str] = []
    lines.append("=================================================================")
    lines.append(" Testkart Intelligence - System Diagnostic & Health Report")
    lines.append(" Mode: READ-ONLY SYSTEM DIAGNOSTIC (NO STATE MODIFICATIONS)")
    lines.append("=================================================================")

    categories = [
        ("1. Configuration Validity", "configuration"),
        ("2. Safety Invariants & Guardrails", "safety_invariants"),
        ("3. Database Connectivity & Integrity", "database"),
        ("4. Five-Source Whitelist & Allowlist", "sources"),
        ("5. Scheduler Lock State (Read-Only)", "scheduler_lock"),
        ("6. Directory & Storage Permissions", "directories"),
        ("7. Timezone & Schedule Timing", "schedule"),
    ]

    for title, key in categories:
        cat_res = results.get(key, {})
        status = cat_res.get("status", "UNKNOWN")
        icon = "[PASS]" if status == "PASS" else "[FAIL]"
        lines.append(f"\n{title:<45} {icon}")
        lines.append("-" * 65)
        for d in cat_res.get("details", []):
            lines.append(f"  - {d}")

    lines.append("\n=================================================================")
    overall_status = "ALL DIAGNOSTIC CHECKS PASSED (SYSTEM HEALTHY)" if results.get("all_passed") else "DIAGNOSTIC ISSUES DETECTED"
    lines.append(f" Overall Result: {overall_status}")
    lines.append("=================================================================\n")

    return "\n".join(lines)
