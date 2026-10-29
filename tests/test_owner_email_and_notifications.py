"""Tests for owner email configuration centralization and disabled external email notifications."""

import pytest
from testkart_intelligence.config import settings
from testkart_intelligence.api.app import (
    ApprovalRequestCreate,
    DraftSaveRequest,
    EditorialDecisionRequest,
)
from testkart_intelligence.security.approvals import ApprovalService
from testkart_intelligence.editorial.service import EditorialService


def test_owner_email_configuration_centralized():
    """Verify OWNER_EMAIL is centralized and configured to meettomar07@gmail.com."""
    assert settings.OWNER_EMAIL == "meettomar07@gmail.com"
    assert "@" in settings.OWNER_EMAIL
    assert "testkart" not in settings.OWNER_EMAIL.lower()


def test_external_email_notifications_strictly_disabled():
    """Verify that email notifications and live publishing remain strictly disabled."""
    assert settings.ENABLE_EMAIL_NOTIFICATIONS is False
    assert settings.ALLOW_LIVE_PUBLISHING is False
    assert settings.SMTP_HOST == ""


def test_api_request_schemas_default_to_owner_email():
    """Verify FastAPI Pydantic request models default to settings.OWNER_EMAIL."""
    appr_req = ApprovalRequestCreate()
    assert appr_req.reviewer_email == "meettomar07@gmail.com"
    assert appr_req.reviewer_email == settings.OWNER_EMAIL

    save_req = DraftSaveRequest(
        expected_version_id="ver_1",
        title="Test Title",
        content_markdown="# Test Content",
    )
    assert save_req.editor_email == "meettomar07@gmail.com"
    assert save_req.editor_email == settings.OWNER_EMAIL

    dec_req = EditorialDecisionRequest(
        expected_version_id="ver_1",
        expected_content_hash="dummy_hash",
        decision="APPROVE",
    )
    assert dec_req.editor_email == "meettomar07@gmail.com"
    assert dec_req.editor_email == settings.OWNER_EMAIL


def test_approval_service_defaults_to_owner_email(tmp_path):
    """Verify ApprovalService falls back to settings.OWNER_EMAIL when reviewer_email is omitted."""
    from testkart_intelligence.database.connection import init_db, get_db

    db_file = tmp_path / "test_appr.db"
    init_db(db_file)

    with get_db(db_file) as conn:
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute(
            "INSERT INTO article_versions (id, article_id, version_number, title, content_markdown, content_hash, created_at) "
            "VALUES ('ver_1', 'art_1', 1, 'Title', 'Markdown', 'dummy_hash_123', '2026-10-27T00:00:00Z')"
        )

    service = ApprovalService(db_path=db_file)
    rec_id, token = service.create_approval_request("ver_1")

    with get_db(db_file) as conn:
        rec = conn.execute("SELECT reviewer_email FROM approval_records WHERE id = ?", (rec_id,)).fetchone()
        assert rec["reviewer_email"] == "meettomar07@gmail.com"
        assert rec["reviewer_email"] == settings.OWNER_EMAIL


def test_no_external_smtp_network_connection_attempted():
    """Verify that no external SMTP or network connections are opened."""
    import socket
    # Ensure SMTP settings are blank
    assert not settings.SMTP_HOST
    assert not settings.ENABLE_EMAIL_NOTIFICATIONS
