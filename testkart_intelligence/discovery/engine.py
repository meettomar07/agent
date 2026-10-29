"""Discovery Engine orchestrating source scans, deduplication, revision handling, and scan logging."""

import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3

from testkart_intelligence.database.connection import get_db
from testkart_intelligence.discovery.fetcher import SafeFetcher, FetchError, SoftErrorPageDetected
from testkart_intelligence.discovery.parser import ListingParser
from testkart_intelligence.discovery.deduplication import DeduplicationEngine, MatchType
from testkart_intelligence.registry.service import SourceRegistryService
from testkart_intelligence.security.allowlist import SecurityValidationError


class DiscoveryEngine:
    """Orchestrates scheduled and manual scans across official government portals."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        fetcher: Optional[SafeFetcher] = None,
    ):
        self.db_path = db_path
        self.fetcher = fetcher or SafeFetcher()
        self.registry = SourceRegistryService(db_path)
        self.recover_orphaned_scans()

    def recover_orphaned_scans(self) -> int:
        """Mark any previously running scan runs as FAILED upon process restart."""
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    UPDATE scan_runs
                    SET status = 'FAILED',
                        completed_at = ?,
                        error_summary = 'Process terminated before scan completion (Recovered on startup)'
                    WHERE status = 'RUNNING'
                    """,
                    (now_iso,),
                )
                return cursor.rowcount
        except Exception:
            return 0

    def run_scan(
        self,
        scan_type: str = "MANUAL",
        source_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a discovery scan across enabled official sources.

        Distinguishes:
        - SUCCESS_NEW: Valid scan, found new or revised notices.
        - SUCCESS_NO_NEW: Valid scan, no new notices found.
        - FAILED: Fetch or parsing failed, soft error detected, or security error logged.
        """
        scan_id = f"scan_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        with get_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO scan_runs (
                    id, scan_type, status, started_at, sources_checked, notices_found, errors_count
                ) VALUES (?, ?, 'RUNNING', ?, 0, 0, 0)
                """,
                (scan_id, scan_type, now_iso),
            )

        sources_to_check: List[Dict[str, Any]] = []
        if source_code:
            src = self.registry.get_source_by_code(source_code)
            if src:
                sources_to_check.append(src)
        else:
            sources_to_check = self.registry.list_sources(enabled_only=True)

        # Restrict discovery scans strictly to the 5 approved authorities
        APPROVED_SOURCES = {"UPSC", "SSC", "NTA", "UPPSC", "TNPSC"}
        sources_to_check = [s for s in sources_to_check if s.get("code") in APPROVED_SOURCES]

        sources_checked = 0
        total_new_notices = 0
        total_revisions = 0
        total_errors = 0
        error_summaries: List[str] = []

        for source in sources_to_check:
            sources_checked += 1
            source_id = source["id"]
            listing_url = source["listing_url"]
            source_code_val = source["code"]
            source_name = source["name"]
            category = source["category"]
            state = source["state"]

            log_id = f"log_{uuid.uuid4().hex[:12]}"
            check_time_iso = datetime.now(timezone.utc).isoformat()
            source_notices_found = 0

            try:
                # 1. Fetch official listing page
                content_bytes, content_type, final_url, elapsed_ms = self.fetcher.fetch(listing_url)
                html_text = content_bytes.decode("utf-8", errors="replace")

                # 2. Parse candidate notice links
                candidates = ListingParser.parse_listing(html_text, final_url)

                # 3. Process candidates with deduplication and revision tracking
                with get_db(self.db_path) as conn:
                    dedup = DeduplicationEngine(conn)

                    for cand in candidates:
                        match_type, existing_id, last_v_num = dedup.evaluate_candidate(
                            source_id=source_id,
                            normalized_url=cand["url"],
                            notice_number=cand.get("notice_number"),
                            title=cand.get("title"),
                        )

                        if match_type == MatchType.NEW:
                            notice_id = f"not_{uuid.uuid4().hex[:12]}"
                            conn.execute(
                                """
                                INSERT INTO canonical_notices (
                                    id, source_id, authority_name, notice_number,
                                    title, normalized_url, category, state, status,
                                    first_discovered_at, last_updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DISCOVERED', ?, ?)
                                """,
                                (
                                    notice_id,
                                    source_id,
                                    source_name,
                                    cand.get("notice_number"),
                                    cand["title"],
                                    cand["url"],
                                    category,
                                    state,
                                    check_time_iso,
                                    check_time_iso,
                                ),
                            )
                            source_notices_found += 1
                            total_new_notices += 1

                        elif match_type == MatchType.REVISION and existing_id:
                            # Flag existing canonical notice as REVISION_DETECTED
                            conn.execute(
                                """
                                UPDATE canonical_notices
                                SET status = 'REVISION_DETECTED',
                                    last_updated_at = ?
                                WHERE id = ?
                                """,
                                (check_time_iso, existing_id),
                            )
                            source_notices_found += 1
                            total_revisions += 1

                    # Record source scan log
                    status = "SUCCESS_NEW" if source_notices_found > 0 else "SUCCESS_NO_NEW"
                    conn.execute(
                        """
                        INSERT INTO scan_source_logs (
                            id, scan_run_id, source_id, status, notices_found_count,
                            response_time_ms, checked_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (log_id, scan_id, source_id, status, source_notices_found, int(elapsed_ms), check_time_iso),
                    )

                # Update source registry success
                self.registry.record_scan_result(source_id, success=True)

            except Exception as exc:
                total_errors += 1
                err_msg = str(exc)
                error_summaries.append(f"[{source_code_val}] {err_msg}")

                with get_db(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT INTO scan_source_logs (
                            id, scan_run_id, source_id, status, notices_found_count,
                            response_time_ms, error_message, checked_at
                        ) VALUES (?, ?, ?, 'FAILED', 0, 0, ?, ?)
                        """,
                        (log_id, scan_id, source_id, err_msg, check_time_iso),
                    )

                self.registry.record_scan_result(source_id, success=False, error_message=err_msg)

        # Finalize scan run record
        completed_at_iso = datetime.now(timezone.utc).isoformat()
        overall_status = "FAILED" if total_errors == sources_checked and sources_checked > 0 else "COMPLETED"

        with get_db(self.db_path) as conn:
            conn.execute(
                """
                UPDATE scan_runs
                SET status = ?,
                    completed_at = ?,
                    sources_checked = ?,
                    notices_found = ?,
                    errors_count = ?,
                    error_summary = ?
                WHERE id = ?
                """,
                (
                    overall_status,
                    completed_at_iso,
                    sources_checked,
                    total_new_notices + total_revisions,
                    total_errors,
                    "; ".join(error_summaries) if error_summaries else None,
                    scan_id,
                ),
            )

        return {
            "scan_id": scan_id,
            "status": overall_status,
            "sources_checked": sources_checked,
            "notices_found": total_new_notices + total_revisions,
            "new_notices": total_new_notices,
            "revisions_found": total_revisions,
            "errors_count": total_errors,
            "error_summary": error_summaries,
            "started_at": now_iso,
            "completed_at": completed_at_iso,
        }
