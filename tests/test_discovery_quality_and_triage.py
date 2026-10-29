"""Acceptance and regression tests for discovery quality audit, triage, recency categorization, and review flagging."""

import json
from datetime import date
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory
from testkart_intelligence.editorial.service import EditorialService
from testkart_intelligence.config import settings
from testkart_intelligence.api.app import app


@pytest.fixture
def triage_test_setup(tmp_path: Path, monkeypatch):
    """Isolated database environment for triage and filter testing."""
    db_file = tmp_path / "triage_test.db"
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    monkeypatch.setattr(settings, "DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path)

    init_db(db_file)
    with get_db(db_file) as conn:
        seed_sources_if_empty(conn)

        # 1. Current active opportunity
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, application_start_date, application_end_date,
                recency_status, triage_flag, triage_notes,
                first_discovered_at, last_updated_at
            ) VALUES (
                'cn_curr_1', 'src_upsc', 'Union Public Service Commission', '08/2026-CAPF',
                'Central Armed Police Forces (ACs) Examination 2026',
                'https://upsc.gov.in/capf2026.pdf', 'Central', 'Central',
                'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
                '2026-09-15', '2026-09-15', '2026-11-15',
                'CURRENT', 'NONE', NULL,
                '2026-10-27T06:00:00Z', '2026-10-27T06:00:00Z'
            )
            """
        )

        # 2. Historical archive record (from 2021)
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, application_start_date, application_end_date,
                recency_status, triage_flag, triage_notes,
                first_discovered_at, last_updated_at
            ) VALUES (
                'cn_hist_1', 'src_nta', 'National Testing Agency', 'NTA/2021/01',
                'Public Notice: Conduct of Examination 2021',
                'https://nta.ac.in/Notice_202105151234.pdf', 'Central', 'Central',
                'OTHER_ANNOUNCEMENT', 'DISCOVERED',
                '2021-05-15', NULL, NULL,
                'HISTORICAL', 'NONE', NULL,
                '2026-10-27T06:00:00Z', '2026-10-27T06:00:00Z'
            )
            """
        )

        # 3. Expired notice (deadline passed in 2026)
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, application_start_date, application_end_date,
                recency_status, triage_flag, triage_notes,
                first_discovered_at, last_updated_at
            ) VALUES (
                'cn_exp_1', 'src_ssc', 'Staff Selection Commission', 'SSC/2026/02',
                'Combined Higher Secondary Level Examination 2026',
                'https://ssc.gov.in/chsl-2026.pdf', 'Central', 'Central',
                'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
                '2026-01-10', '2026-01-10', '2026-02-15',
                'EXPIRED', 'NONE', NULL,
                '2026-10-27T06:00:00Z', '2026-10-27T06:00:00Z'
            )
            """
        )

        # 4. Notice needing classification review
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, application_start_date, application_end_date,
                recency_status, triage_flag, triage_notes,
                first_discovered_at, last_updated_at
            ) VALUES (
                'cn_flag_1', 'src_uppsc', 'Uttar Pradesh Public Service Commission', 'A-1/E-1/2026',
                'Notice regarding Advt No A-1/E-1/2026',
                'https://uppsc.up.nic.in/notice_123.pdf', 'State', 'Uttar Pradesh',
                'OTHER_ANNOUNCEMENT', 'DISCOVERED',
                '2026-10-10', NULL, NULL,
                'CURRENT', 'NONE', NULL,
                '2026-10-27T06:00:00Z', '2026-10-27T06:00:00Z'
            )
            """
        )

    return {"db_file": db_file}


def test_notice_triage_recency_and_dates():
    """Verify that date extraction accurately partitions current, expired, historical, and unknown notices."""
    ref_date = date(2026, 10, 27)

    # 1. Historical NTA notice from 2021
    pub, start, end, recency = NoticeClassifier.extract_dates(
        title="Public Notice for UGC-NET Dec 2020 and June 2021",
        url="https://nta.ac.in/Notice_20210810123456.pdf",
        ref_date=ref_date,
    )
    assert recency == "HISTORICAL"
    assert pub == "2021-08-10"

    # 2. Historical notice by year in title
    pub2, start2, end2, recency2 = NoticeClassifier.extract_dates(
        title="Recruitment Notification 2019 for Assistant Engineers",
        url="https://tnpsc.gov.in/notices/ae_2019.pdf",
        ref_date=ref_date,
    )
    assert recency2 == "HISTORICAL"

    # 3. Current active opportunity in October 2026
    pub3, start3, end3, recency3 = NoticeClassifier.extract_dates(
        title="Combined Geo-Scientist Examination 2026",
        url="https://upsc.gov.in/geo_2026_10_15.pdf",
        ref_date=ref_date,
    )
    assert recency3 == "CURRENT"

    # 4. Expired notice with past 2026 deadline
    pub4, start4, end4, recency4 = NoticeClassifier.extract_dates(
        title="Notice 01/2026 Last Date: 15/02/2026",
        url="https://ssc.gov.in/notice.pdf",
        ref_date=ref_date,
    )
    assert recency4 == "EXPIRED"

    # 5. Unknown notice with no date markers
    pub5, start5, end5, recency5 = NoticeClassifier.extract_dates(
        title="General Guidelines for Examination Candidates",
        url="https://upsc.gov.in/guidelines.pdf",
        ref_date=ref_date,
    )
    assert recency5 == "UNKNOWN"
    assert pub5 is None


def test_triage_and_filter_views_via_api(triage_test_setup):
    """Verify editorial web interface and REST API multi-field filtering."""
    client = TestClient(app)

    # 1. Filter by recency=CURRENT
    resp = client.get("/editorial/notices?recency=CURRENT")
    assert resp.status_code == 200
    html = resp.text
    assert "Central Armed Police Forces" in html
    assert "Conduct of Examination 2021" not in html

    # 2. Filter by authority=UPSC
    resp = client.get("/editorial/notices?authority=UPSC")
    assert resp.status_code == 200
    assert "Union Public Service Commission" in resp.text
    assert "National Testing Agency" not in resp.text

    # 3. Filter by category=RECRUITMENT_NOTIFICATION
    resp = client.get("/editorial/notices?category=RECRUITMENT_NOTIFICATION")
    assert resp.status_code == 200
    assert "Combined Higher Secondary Level" in resp.text
    assert "Conduct of Examination 2021" not in resp.text

    # 4. JSON API endpoint /api/notices filtering
    api_resp = client.get("/api/notices?recency=HISTORICAL")
    assert api_resp.status_code == 200
    data = api_resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "cn_hist_1"


def test_flag_notice_for_review_and_audit_logging(triage_test_setup):
    """Verify human reviewers can flag notices with audit logs and reclassification."""
    client = TestClient(app)

    payload = {
        "flag": "MISCLASSIFIED",
        "notes": "Title indicates recruitment advertisement, not generic announcement",
        "proposed_category": "RECRUITMENT_NOTIFICATION",
        "author": "lead_editor",
    }

    resp = client.post("/api/editorial/notices/cn_flag_1/flag", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "success"
    assert res_data["flag"] == "MISCLASSIFIED"

    # Verify database update
    with get_db(triage_test_setup["db_file"]) as conn:
        row = conn.execute(
            "SELECT classification, triage_flag, triage_notes FROM canonical_notices WHERE id = 'cn_flag_1'"
        ).fetchone()
        assert row["classification"] == "RECRUITMENT_NOTIFICATION"
        assert row["triage_flag"] == "MISCLASSIFIED"
        assert "Title indicates" in row["triage_notes"]

        # Verify audit event insertion
        audit = conn.execute(
            "SELECT * FROM audit_events WHERE entity_id = 'cn_flag_1' AND action = 'NOTICE_FLAGGED_FOR_REVIEW'"
        ).fetchone()
        assert audit is not None
        assert audit["actor"] == "lead_editor"


def test_editorial_dashboard_metrics_with_triage_counts(triage_test_setup):
    """Verify dashboard overview renders actionable opportunities and archive distinction."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "Actionable Current Opportunities" in html
    assert "Historical Portal Archives" in html
    assert "Portal Archive Architecture Notice" in html
