"""Multi-factor notice deduplication and revision detection."""

import sqlite3
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class MatchType(str, Enum):
    NEW = "NEW"
    UNCHANGED = "UNCHANGED"
    REVISION = "REVISION"


class DeduplicationEngine:
    """Evaluates candidate notices against existing database records to prevent duplicates and detect revisions."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def evaluate_candidate(
        self,
        source_id: str,
        normalized_url: str,
        notice_number: Optional[str] = None,
        title: Optional[str] = None,
        new_doc_hash: Optional[str] = None,
    ) -> Tuple[MatchType, Optional[str], Optional[int]]:
        """Evaluate a candidate notice against existing records.

        Returns:
            Tuple of (MatchType, existing_canonical_notice_id, latest_version_number)
        """
        existing_notice = None

        # Check 1: Match by exact normalized URL under same authority
        cursor = self.conn.execute(
            """
            SELECT id, notice_number, title
            FROM canonical_notices
            WHERE source_id = ? AND normalized_url = ?
            """,
            (source_id, normalized_url),
        )
        existing_notice = cursor.fetchone()

        # Check 2: Match by notice number under same authority if notice_number exists
        if not existing_notice and notice_number:
            cursor = self.conn.execute(
                """
                SELECT id, notice_number, title
                FROM canonical_notices
                WHERE source_id = ? AND notice_number = ? AND notice_number != ''
                """,
                (source_id, notice_number),
            )
            existing_notice = cursor.fetchone()

        # If no existing notice found, this is completely new
        if not existing_notice:
            return MatchType.NEW, None, None

        canonical_id = existing_notice["id"]

        # Fetch latest version for this notice
        v_cursor = self.conn.execute(
            """
            SELECT version_number, document_hash
            FROM notice_versions
            WHERE notice_id = ?
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (canonical_id,),
        )
        latest_version = v_cursor.fetchone()

        if not latest_version:
            # Notice exists in canonical_notices but no document version recorded yet
            return MatchType.UNCHANGED, canonical_id, 0

        latest_v_num = latest_version["version_number"]
        latest_hash = latest_version["document_hash"]

        # If new document hash is provided, compare hashes
        if new_doc_hash:
            if new_doc_hash == latest_hash:
                return MatchType.UNCHANGED, canonical_id, latest_v_num
            else:
                # Document content has changed -> Revised notification!
                return MatchType.REVISION, canonical_id, latest_v_num

        # Without document hash, if URL/notice_number matched existing notice, consider unchanged
        return MatchType.UNCHANGED, canonical_id, latest_v_num
