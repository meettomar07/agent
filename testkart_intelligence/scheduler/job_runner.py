"""Scheduler for automated twice-daily discovery scans in Asia/Kolkata timezone."""

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional
import psutil
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from testkart_intelligence.config import settings
from testkart_intelligence.discovery.engine import DiscoveryEngine

logger = logging.getLogger("testkart.scheduler")
# Prevent CPython 3.13 Windows frame-walking crash during test execution
logger.findCaller = lambda *args, **kwargs: ("(job_runner)", 0, "scan_job", None)


class SchedulerAlreadyRunningError(Exception):
    """Raised when an attempt is made to start multiple concurrent scheduler instances."""
    pass


class ScanScheduler:
    """Manages scheduled discovery scans with overlap prevention, duplicate instance protection, and history persistence."""

    _active_instance: Optional["ScanScheduler"] = None
    _instance_lock = threading.Lock()

    def __init__(self, db_path=None):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.lock_file = (Path(self.db_path).parent if self.db_path else settings.DATA_DIR) / "scheduler.lock"
        self.scheduler = BackgroundScheduler(timezone=settings.TIMEZONE)
        self.engine = DiscoveryEngine(db_path=self.db_path)

    @property
    def is_running(self) -> bool:
        """Check if scheduler is currently running."""
        return self.scheduler.running

    def scan_job(self) -> None:
        """Scheduled scan wrapper with overlap prevention and error recovery."""
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            logger.warning("Scheduled scan skipped: another scan job is currently in progress.")
            return

        try:
            # Check for any missed scan windows (e.g. machine was asleep)
            self.engine.check_and_record_missed_windows()
            # Recover any orphaned scans from prior terminated processes
            self.engine.recover_orphaned_scans()
            logger.info("Starting scheduled discovery scan (Asia/Kolkata)...")
            result = self.engine.run_scan(scan_type="SCHEDULED")
            logger.info(
                f"Scheduled scan completed: ID={result['scan_id']}, "
                f"Sources={result['sources_checked']}, Notices={result['notices_found']}, Errors={result['errors_count']}"
            )
        except Exception as exc:
            logger.error(f"Error during scheduled scan: {exc}", exc_info=True)
        finally:
            self._lock.release()

    def start(self) -> None:
        """Configure cron trigger for twice-daily execution and start scheduler.

        Guards:
        - Prevents duplicate scheduler instances (in-process and cross-process).
        - Preserves strict 06:00 and 18:00 Asia/Kolkata cron trigger.
        """
        with ScanScheduler._instance_lock:
            if ScanScheduler._active_instance is not None and ScanScheduler._active_instance.is_running:
                raise SchedulerAlreadyRunningError(
                    "A ScanScheduler instance is already active and running. Multiple concurrent schedulers are prevented."
                )

            # Cross-process lock verification
            if self.lock_file.exists():
                try:
                    with open(self.lock_file, "r", encoding="utf-8") as f:
                        pid_str = f.read().strip()
                    if pid_str:
                        pid = int(pid_str)
                        if psutil.pid_exists(pid) and pid != os.getpid():
                            raise SchedulerAlreadyRunningError(
                                f"A ScanScheduler process is already running in another process (PID {pid}, lock file: {self.lock_file}). "
                                "Multiple concurrent schedulers are prevented."
                            )
                except SchedulerAlreadyRunningError:
                    raise
                except Exception:
                    pass

            # Detect any missed scan windows from prior downtime
            self.engine.check_and_record_missed_windows()

            hours_str = ",".join(str(h) for h in settings.SCAN_HOURS)
            trigger = CronTrigger(
                hour=hours_str,
                minute=settings.SCAN_MINUTES,
                timezone=settings.TIMEZONE,
            )

            self.scheduler.add_job(
                self.scan_job,
                trigger=trigger,
                id="twice_daily_discovery_scan",
                name="Twice Daily Official Notice Discovery",
                replace_existing=True,
            )

            self.scheduler.start()
            ScanScheduler._active_instance = self

            # Acquire lock file
            try:
                self.lock_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.lock_file, "w", encoding="utf-8") as f:
                    f.write(str(os.getpid()))
            except Exception as e:
                logger.warning(f"Could not write scheduler lock file {self.lock_file}: {e}")

        logger.info(
            f"Scheduler active: twice daily scans configured for hours [{hours_str}] "
            f"at minute {settings.SCAN_MINUTES} ({settings.TIMEZONE})"
        )

    def shutdown(self) -> None:
        """Stop scheduler and release active instance registration and lock file."""
        with ScanScheduler._instance_lock:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            if ScanScheduler._active_instance is self:
                ScanScheduler._active_instance = None

            if self.lock_file.exists():
                try:
                    with open(self.lock_file, "r", encoding="utf-8") as f:
                        pid_str = f.read().strip()
                    if pid_str and int(pid_str) == os.getpid():
                        self.lock_file.unlink(missing_ok=True)
                except Exception:
                    pass
        logger.info("ScanScheduler successfully stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Return runtime diagnostic status and calculated next fire times."""
        job = self.scheduler.get_job("twice_daily_discovery_scan")
        next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
        return {
            "running": self.is_running,
            "timezone": settings.TIMEZONE,
            "scan_hours": settings.SCAN_HOURS,
            "scan_minutes": settings.SCAN_MINUTES,
            "next_run_time": next_run,
            "is_locked": self._lock.locked(),
        }
