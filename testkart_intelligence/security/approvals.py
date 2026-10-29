"""Security approval workflow with immutable content-hash binding and audit trails."""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import sqlite3

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import get_db


class ApprovalSecurityError(Exception):
    """Raised when approval verification fails."""
    pass


class ApprovalService:
    """Manages token creation, hash validation, and human decision recording."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def create_approval_request(
        self,
        article_version_id: str,
        reviewer_email: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generate a single-use approval token bound to an immutable content hash.

        Returns:
            Tuple of (approval_record_id, raw_token)
        """
        reviewer_email = (reviewer_email or settings.OWNER_EMAIL).strip()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.APPROVAL_TOKEN_EXPIRY_HOURS)

        with get_db(self.db_path) as conn:
            # Fetch article version content hash
            row = conn.execute(
                "SELECT content_hash, article_id FROM article_versions WHERE id = ?",
                (article_version_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Article version {article_version_id} not found")

            content_hash = row["content_hash"]
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            record_id = f"appr_{uuid.uuid4().hex[:12]}"

            conn.execute(
                """
                INSERT INTO approval_records (
                    id, article_version_id, content_hash, token_hash, reviewer_email,
                    status, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (
                    record_id,
                    article_version_id,
                    content_hash,
                    token_hash,
                    reviewer_email,
                    expires_at.isoformat(),
                    now.isoformat(),
                ),
            )

            # Audit event
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, entity_type, entity_id, action, actor, payload_json, timestamp
                ) VALUES (?, 'approval_record', ?, 'APPROVAL_REQUEST_CREATED', ?, ?, ?)
                """,
                (
                    f"aud_{uuid.uuid4().hex[:12]}",
                    record_id,
                    reviewer_email,
                    f'{{"article_version_id": "{article_version_id}", "content_hash": "{content_hash}"}}',
                    now.isoformat(),
                ),
            )

        return record_id, raw_token

    def decide_approval(
        self,
        raw_token: str,
        decision: str,  # "APPROVED" | "REJECTED"
        decision_notes: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process explicit human approval/rejection.

        Validates:
        - Token existence and expiry
        - Content hash integrity (must match version's current hash)
        - Prevents replay (single-use)
        """
        if decision not in ("APPROVED", "REJECTED"):
            raise ApprovalSecurityError(f"Invalid decision '{decision}'. Must be APPROVED or REJECTED.")

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        with get_db(self.db_path) as conn:
            record = conn.execute(
                "SELECT * FROM approval_records WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()

            if not record:
                raise ApprovalSecurityError("Invalid or unknown approval token")

            if record["status"] != "PENDING":
                raise ApprovalSecurityError(f"Approval token has already been used (status: {record['status']})")

            # Check expiry
            expires_at = datetime.fromisoformat(record["expires_at"])
            if now > expires_at:
                conn.execute("UPDATE approval_records SET status = 'EXPIRED' WHERE id = ?", (record["id"],))
                conn.commit()
                raise ApprovalSecurityError("Approval token has expired")

            # Validate content hash has not changed
            v_row = conn.execute(
                "SELECT content_hash, article_id FROM article_versions WHERE id = ?",
                (record["article_version_id"],),
            ).fetchone()

            if not v_row or v_row["content_hash"] != record["content_hash"]:
                conn.execute("UPDATE approval_records SET status = 'INVALIDATED' WHERE id = ?", (record["id"],))
                conn.commit()
                raise ApprovalSecurityError("Content hash mismatch: Article version has changed or been altered")

            # Record decision
            conn.execute(
                """
                UPDATE approval_records
                SET status = ?, decided_at = ?, decision_notes = ?, client_ip = ?
                WHERE id = ?
                """,
                (decision, now_iso, decision_notes, client_ip, record["id"]),
            )

            # Update article status
            art_status = "APPROVED" if decision == "APPROVED" else "REJECTED"
            conn.execute(
                "UPDATE blog_articles SET status = ?, updated_at = ? WHERE id = ?",
                (art_status, now_iso, v_row["article_id"]),
            )

            # Audit log
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, entity_type, entity_id, action, actor, payload_json, timestamp
                ) VALUES (?, 'approval_record', ?, ?, ?, ?, ?)
                """,
                (
                    f"aud_{uuid.uuid4().hex[:12]}",
                    record["id"],
                    f"DECISION_{decision}",
                    record["reviewer_email"],
                    f'{{"decision": "{decision}", "notes": "{decision_notes}"}}',
                    now_iso,
                ),
            )

            return {
                "approval_id": record["id"],
                "decision": decision,
                "article_id": v_row["article_id"],
                "article_version_id": record["article_version_id"],
                "decided_at": now_iso,
            }
