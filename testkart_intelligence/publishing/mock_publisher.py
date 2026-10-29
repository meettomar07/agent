"""Mock Publisher for local testing and verification."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import sqlite3

from testkart_intelligence.database.connection import get_db
from testkart_intelligence.publishing.base import PublisherInterface
from testkart_intelligence.publishing.guard import assert_live_publishing_disabled


class MockPublishingError(Exception):
    """Raised when mock publishing preconditions are violated."""
    pass


class MockPublisher(PublisherInterface):
    """Mock publisher that simulates publishing while strictly ensuring live publishing remains disabled."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def publish(
        self,
        article_version_id: str,
        content_hash: str,
        approval_record_id: str,
    ) -> Dict[str, Any]:
        """Execute mock publication with security assertions and idempotency.

        Preconditions:
        - Live publishing is disabled (failsafe check)
        - Approval record is APPROVED
        - Content hash matches approved record
        """
        assert_live_publishing_disabled()
        now_iso = datetime.now(timezone.utc).isoformat()

        with get_db(self.db_path) as conn:
            # 1. Check existing completed job (Idempotency)
            existing_job = conn.execute(
                """
                SELECT * FROM publishing_jobs
                WHERE article_version_id = ? AND status = 'COMPLETED'
                """,
                (article_version_id,),
            ).fetchone()

            if existing_job:
                return {
                    "job_id": existing_job["id"],
                    "status": "COMPLETED",
                    "published_url": existing_job["published_url"],
                    "is_mock": True,
                    "idempotent": True,
                }

            # 2. Verify approval record
            approval = conn.execute(
                "SELECT * FROM approval_records WHERE id = ?",
                (approval_record_id,),
            ).fetchone()

            if not approval:
                raise MockPublishingError(f"Approval record {approval_record_id} does not exist")

            if approval["status"] != "APPROVED":
                raise MockPublishingError(
                    f"Cannot publish unapproved draft. Approval status is '{approval['status']}'"
                )

            if approval["content_hash"] != content_hash:
                raise MockPublishingError("Content hash mismatch between approval and publication request")

            # 3. Fetch article slug
            art_row = conn.execute(
                """
                SELECT ba.slug, ba.title
                FROM blog_articles ba
                JOIN article_versions av ON av.article_id = ba.id
                WHERE av.id = ?
                """,
                (article_version_id,),
            ).fetchone()

            slug = art_row["slug"] if art_row else "article"
            published_url = f"https://mock.testkart.local/blog/{slug}"
            job_id = f"job_{uuid.uuid4().hex[:12]}"

            conn.execute(
                """
                INSERT INTO publishing_jobs (
                    id, article_version_id, approval_record_id, publisher_name,
                    is_mock, status, attempt_count, published_url, response_payload,
                    created_at, executed_at
                ) VALUES (?, ?, ?, 'mock_publisher', 1, 'COMPLETED', 1, ?, '{"mock_response": "200 OK"}', ?, ?)
                """,
                (job_id, article_version_id, approval_record_id, published_url, now_iso, now_iso),
            )

            # Audit event
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, entity_type, entity_id, action, actor, payload_json, timestamp
                ) VALUES (?, 'publishing_job', ?, 'MOCK_PUBLISHED', 'mock_publisher', ?, ?)
                """,
                (
                    f"aud_{uuid.uuid4().hex[:12]}",
                    job_id,
                    f'{{"article_version_id": "{article_version_id}", "published_url": "{published_url}"}}',
                    now_iso,
                ),
            )

            return {
                "job_id": job_id,
                "status": "COMPLETED",
                "published_url": published_url,
                "is_mock": True,
                "idempotent": False,
            }
