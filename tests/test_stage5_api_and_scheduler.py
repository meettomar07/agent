"""Unit tests for Stage 5: FastAPI endpoints and Scheduler Runner."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.api.app import app
from testkart_intelligence.scheduler.job_runner import ScanScheduler
from testkart_intelligence.config import settings


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    test_db = tmp_path / "test_api.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    init_db(test_db)
    with get_db(test_db) as conn:
        seed_sources_if_empty(conn)
    return TestClient(app)


def test_api_system_status(client: TestClient):
    """Verify system status metrics and hard guard for live publishing."""
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()

    assert data["live_publishing_enabled"] is False
    assert data["sources"]["total"] >= 10
    assert data["sources"]["active"] >= 5


def test_api_list_and_toggle_sources(client: TestClient):
    """Verify source listing and toggle enable/disable."""
    resp = client.get("/api/sources")
    assert resp.status_code == 200
    sources = resp.json()
    assert len(sources) >= 10

    # Toggle disable
    resp_toggle = client.post("/api/sources/src_upsc/toggle?enabled=false")
    assert resp_toggle.status_code == 200

    resp_sources_enabled = client.get("/api/sources?enabled_only=true")
    enabled_ids = [s["id"] for s in resp_sources_enabled.json()]
    assert "src_upsc" not in enabled_ids

    # Toggle back on
    client.post("/api/sources/src_upsc/toggle?enabled=true")


def test_api_html_dashboard(client: TestClient):
    """Verify HTML dashboard renders successfully."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Testkart Intelligence" in resp.text
    assert "LIVE PUBLISHING DISABLED" in resp.text


def test_scheduler_overlap_prevention(tmp_path: Path):
    """Verify that concurrent calls to scan_job are safely locked to prevent overlapping runs."""
    scheduler = ScanScheduler(db_path=tmp_path / "test_sched.db")

    # Acquire lock manually to simulate an active running scan
    acquired = scheduler._lock.acquire(blocking=False)
    assert acquired is True

    # Mock engine scan
    scheduler.engine.run_scan = MagicMock()

    # Trigger second scan while lock is held
    scheduler.scan_job()

    # Engine must NOT have been called because job was locked
    scheduler.engine.run_scan.assert_not_called()

    # Release lock
    scheduler._lock.release()

    # Trigger scan when lock is free
    scheduler.scan_job()
    scheduler.engine.run_scan.assert_called_once()
