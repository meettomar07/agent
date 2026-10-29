"""Official Source Registry management service."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3

from testkart_intelligence.database.connection import get_db
from testkart_intelligence.security.allowlist import validate_official_url, extract_domain, is_official_domain


SEED_SOURCES_PATH = Path(__file__).resolve().parent / "sources.json"


def seed_sources_if_empty(conn: sqlite3.Connection) -> int:
    """Populate official sources table from sources.json if empty or missing entries."""
    if not SEED_SOURCES_PATH.exists():
        return 0

    with open(SEED_SOURCES_PATH, "r", encoding="utf-8") as f:
        seed_data: List[Dict[str, Any]] = json.load(f)

    inserted_or_updated = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for item in seed_data:
        # Validate domain before seeding
        validate_official_url(item["listing_url"])
        domain = extract_domain(item["listing_url"])

        conn.execute(
            """
            INSERT INTO official_sources (
                id, code, name, category, state, official_domain, listing_url,
                retrieval_method, verification_status, enabled, consecutive_failures,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                state = excluded.state,
                official_domain = excluded.official_domain,
                listing_url = excluded.listing_url,
                retrieval_method = excluded.retrieval_method,
                verification_status = excluded.verification_status,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (
                item["id"],
                item["code"],
                item["name"],
                item["category"],
                item["state"],
                domain,
                item["listing_url"],
                item.get("retrieval_method", "html_scrape"),
                item.get("verification_status", "VERIFIED"),
                1 if item.get("enabled", True) else 0,
                now_iso,
                now_iso,
            ),
        )
        inserted_or_updated += 1

    return inserted_or_updated


class SourceRegistryService:
    """Service for querying and managing official government exam portals."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def list_sources(
        self,
        enabled_only: bool = False,
        category: Optional[str] = None,
        state: Optional[str] = None,
        verification_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List registered official sources with optional filters."""
        query = "SELECT * FROM official_sources WHERE 1=1"
        params: List[Any] = []

        if enabled_only:
            query += " AND enabled = 1"
        if category:
            query += " AND category = ?"
            params.append(category)
        if state:
            query += " AND state = ?"
            params.append(state)
        if verification_status:
            query += " AND verification_status = ?"
            params.append(verification_status)

        query += " ORDER BY category, name"

        with get_db(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_source_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Retrieve source details by unique authority code."""
        with get_db(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM official_sources WHERE code = ?", (code,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_source_by_id(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve source details by primary id."""
        with get_db(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM official_sources WHERE id = ?", (source_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def register_source(
        self,
        code: str,
        name: str,
        category: str,
        state: str,
        listing_url: str,
        retrieval_method: str = "html_scrape",
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """Add and verify a new official source, strictly rejecting non-official domains."""
        # Security validation raises SecurityValidationError if invalid
        validate_official_url(listing_url)
        domain = extract_domain(listing_url)

        source_id = f"src_{code.lower().replace(' ', '_')}"
        now_iso = datetime.now(timezone.utc).isoformat()

        with get_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO official_sources (
                    id, code, name, category, state, official_domain, listing_url,
                    retrieval_method, verification_status, enabled, consecutive_failures,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'VERIFIED', ?, 0, ?, ?)
                """,
                (
                    source_id,
                    code.upper(),
                    name,
                    category,
                    state,
                    domain,
                    listing_url,
                    retrieval_method,
                    1 if enabled else 0,
                    now_iso,
                    now_iso,
                ),
            )
        return self.get_source_by_id(source_id)  # type: ignore

    def set_enabled(self, source_id: str, enabled: bool) -> bool:
        """Enable or disable an official source."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE official_sources SET enabled = ?, updated_at = ? WHERE id = ? OR code = ?",
                (1 if enabled else 0, now_iso, source_id, source_id.upper()),
            )
            return cursor.rowcount > 0

    def record_scan_result(
        self,
        source_id: str,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """Update last checked timestamps and failure counters for a source."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db(self.db_path) as conn:
            if success:
                conn.execute(
                    """
                    UPDATE official_sources
                    SET last_checked_at = ?,
                        last_success_at = ?,
                        consecutive_failures = 0,
                        last_error = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now_iso, now_iso, now_iso, source_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE official_sources
                    SET last_checked_at = ?,
                        consecutive_failures = consecutive_failures + 1,
                        last_error = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now_iso, error_message, now_iso, source_id),
                )
