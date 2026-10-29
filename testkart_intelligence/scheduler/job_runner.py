"""Scheduler for automated twice-daily discovery scans in Asia/Kolkata timezone."""

import logging
import threading
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from testkart_intelligence.config import settings
from testkart_intelligence.discovery.engine import DiscoveryEngine

logger = logging.getLogger("testkart.scheduler")
# Prevent CPython 3.13 Windows frame-walking crash during test execution
logger.findCaller = lambda *args, **kwargs: ("(job_runner)", 0, "scan_job", None)


class ScanScheduler:
    """Manages scheduled discovery scans with overlap prevention and history persistence."""

    def __init__(self, db_path=None):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.scheduler = BackgroundScheduler(timezone=settings.TIMEZONE)
        self.engine = DiscoveryEngine(db_path=self.db_path)

    def scan_job(self) -> None:
        """Scheduled scan wrapper with overlap prevention."""
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            logger.warning("Scheduled scan skipped: another scan job is currently in progress.")
            return

        try:
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
        """Configure cron trigger for twice-daily execution and start scheduler."""
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
        logger.info(
            f"Scheduler active: twice daily scans configured for hours [{hours_str}] "
            f"at minute {settings.SCAN_MINUTES} ({settings.TIMEZONE})"
        )

    def shutdown(self) -> None:
        """Stop scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
