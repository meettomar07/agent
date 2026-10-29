"""Tests for Supervised Editorial Workflow improvements and fact correction/confirmation."""

import hashlib
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.api.app import app
from testkart_intelligence.config import settings
from testkart_intelligence.editorial.service import EditorialService, ApprovalBlockedError


@pytest.fixture
def editorial_env(tmp_path: Path, monkeypatch):
    """Set up test database and mock client with an active article and notice facts."""
    db_file = tmp_path / "editorial_workflow_test.db"
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    monkeypatch.setattr(settings, "DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path)

    init_db(db_file)
    with get_db(db_file) as conn:
        seed_sources_if_empty(conn)

        # Notice
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_wf_1', 'src_upsc', 'Union Public Service Commission', '01/2026',
                'Engineering Services Examination 2026', 'https://upsc.gov.in/ese-2026.pdf',
                'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
                '2026-10-24T06:00:00Z', '2026-10-24T06:00:00Z'
            )
            """
        )

        doc_hash = hashlib.sha256(b"mock ese bytes").hexdigest()
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES (
                'nver_wf_1', 'not_wf_1', 1, 'https://upsc.gov.in/ese-2026.pdf', ?,
                'PDF', 'ese_2026.pdf', 'Engineering services examination 2026 notice', 8, '2026-10-24T06:00:00Z'
            )
            """,
            (doc_hash,),
        )

        # Facts
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence,
                evidence_text, page_number, verified_status, created_at
            ) VALUES
            ('fact_wf_vac', 'nver_wf_1', 'total_vacancies', '200', 0.90, 'Table row: Total vacancies 200', 3, 'VERIFIED', '2026-10-24T06:00:00Z'),
            ('fact_wf_start', 'nver_wf_1', 'application_start_date', '01/11/2026', 0.95, 'Applications commence on 01/11/2026', 1, 'VERIFIED', '2026-10-24T06:00:00Z'),
            ('fact_wf_end', 'nver_wf_1', 'application_end_date', '30/11/2026', 0.95, 'Last date for submission is 30/11/2026', 1, 'VERIFIED', '2026-10-24T06:00:00Z'),
            ('fact_wf_exam', 'nver_wf_1', 'exam_date', '15/02/2027', 0.80, 'Exam on 15/02/2027', 4, 'UNVERIFIED', '2026-10-24T06:00:00Z'),
            ('fact_wf_age', 'nver_wf_1', 'age_limit', '21 to 30 years', 0.90, 'Age limit 21 to 30 years', 2, 'VERIFIED', '2026-10-24T06:00:00Z')
            """
        )

        # Draft Article & Version
        v1_hash = hashlib.sha256(b"v1 markdown content").hexdigest()
        conn.execute(
            """
            INSERT INTO blog_articles (
                id, canonical_notice_id, title, slug, status, template_type, current_version_id, created_at, updated_at
            ) VALUES (
                'art_wf_1', 'not_wf_1', 'UPSC ESE 2026 Recruitment', 'upsc-ese-2026-recruitment',
                'QA_PASSED', 'RECRUITMENT', 'arv_wf_1', '2026-10-24T06:00:00Z', '2026-10-24T06:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO article_versions (
                id, article_id, version_number, content_markdown, content_hash,
                title, generated_by, created_at
            ) VALUES (
                'arv_wf_1', 'art_wf_1', 1, 'v1 markdown content', ?,
                'UPSC ESE 2026 Recruitment', 'system', '2026-10-24T06:00:00Z'
            )
            """,
            (v1_hash,),
        )

        # Pre-approve article to test invalidation upon fact correction
        conn.execute(
            """
            INSERT INTO approval_records (
                id, article_version_id, content_hash, token_hash, reviewer_email,
                status, expires_at, decided_at, decision_notes, client_ip, created_at
            ) VALUES (
                'appr_wf_1', 'arv_wf_1', ?, 'token_hash_1', 'meettomar07@gmail.com',
                'APPROVED', '2026-10-25T06:00:00Z', '2026-10-24T07:00:00Z', 'Approved initially', '127.0.0.1', '2026-10-24T07:00:00Z'
            )
            """,
            (v1_hash,),
        )
        conn.execute("UPDATE blog_articles SET status = 'APPROVED' WHERE id = 'art_wf_1'")

    client = TestClient(app)
    return client, db_file


def test_fact_correction_preserves_original_and_invalidates_approvals(editorial_env):
    """Reviewer fact correction must preserve original machine value, store correction, and invalidate approvals."""
    client, db_file = editorial_env

    # Correct vacancy from 200 to 232
    resp = client.post(
        "/api/editorial/facts/fact_wf_vac/correct",
        json={
            "corrected_value": "232",
            "reason": "Corrigendum issued increasing vacancies across civil and mechanical cadres",
            "reviewer_email": "meettomar07@gmail.com",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fact_id"] == "fact_wf_vac"
    assert data["original_value"] == "200"
    assert data["corrected_value"] == "232"
    assert data["corrected_by"] == "meettomar07@gmail.com"
    assert data["is_confirmed"] is True

    # Check database state
    with get_db(db_file) as conn:
        fact = conn.execute("SELECT * FROM extracted_facts WHERE id = 'fact_wf_vac'").fetchone()
        assert fact["fact_value"] == "200"  # Original preserved!
        assert fact["corrected_value"] == "232"
        assert fact["corrected_by"] == "meettomar07@gmail.com"
        assert fact["correction_reason"] == "Corrigendum issued increasing vacancies across civil and mechanical cadres"
        assert fact["is_confirmed"] == 1
        assert fact["verified_status"] == "VERIFIED"

        # Check fact_corrections_log
        log = conn.execute("SELECT * FROM fact_corrections_log WHERE fact_id = 'fact_wf_vac'").fetchone()
        assert log is not None
        assert log["original_value"] == "200"
        assert log["corrected_value"] == "232"
        assert log["reviewer_email"] == "meettomar07@gmail.com"

        # Check linked article approval was INVALIDATED!
        appr = conn.execute("SELECT status FROM approval_records WHERE id = 'appr_wf_1'").fetchone()
        assert appr["status"] == "INVALIDATED"

        # Check linked article was reset to DRAFT
        art = conn.execute("SELECT status FROM blog_articles WHERE id = 'art_wf_1'").fetchone()
        assert art["status"] == "DRAFT"

        # Check audit event
        ae = conn.execute("SELECT * FROM audit_events WHERE entity_id = 'fact_wf_vac' AND action = 'FACT_CORRECTED'").fetchone()
        assert ae is not None
        assert "232" in ae["payload_json"]


def test_fact_confirmation_marks_confirmed_and_audited(editorial_env):
    """Explicit fact confirmation updates is_confirmed, sets verified status, and logs audit event."""
    client, db_file = editorial_env

    resp = client.post(
        "/api/editorial/facts/fact_wf_exam/confirm",
        json={"reviewer_email": "meettomar07@gmail.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fact_id"] == "fact_wf_exam"
    assert data["is_confirmed"] is True
    assert data["confirmed_by"] == "meettomar07@gmail.com"

    with get_db(db_file) as conn:
        fact = conn.execute("SELECT * FROM extracted_facts WHERE id = 'fact_wf_exam'").fetchone()
        assert fact["is_confirmed"] == 1
        assert fact["confirmed_by"] == "meettomar07@gmail.com"

        ae = conn.execute("SELECT * FROM audit_events WHERE entity_id = 'fact_wf_exam' AND action = 'FACT_CONFIRMED'").fetchone()
        assert ae is not None


def test_critical_fields_summary_in_editorial_views(editorial_env):
    """Notice review and draft editor must surface critical recruitment fields with verification badges."""
    client, db_file = editorial_env
    service = EditorialService(db_path=db_file)

    notice_review = service.get_notice_review("not_wf_1")
    assert "critical_fields_summary" in notice_review
    summary = {cf["field_key"]: cf for cf in notice_review["critical_fields_summary"]}

    assert "total_vacancies" in summary
    assert "application_start_date" in summary
    assert "application_end_date" in summary
    assert "exam_date" in summary
    assert "eligibility" in summary

    # Eligibility was not inserted, so it should be flagged MISSING
    assert summary["eligibility"]["flag"] == "MISSING"
    assert summary["eligibility"]["is_low_confidence"] is True

    # HTML routes should render without error
    resp_notice = client.get("/editorial/notices/not_wf_1")
    assert resp_notice.status_code == 200
    assert "Critical Recruitment Fields Verification" in resp_notice.text
    assert "total_vacancies" in resp_notice.text

    resp_editor = client.get("/editorial/articles/art_wf_1")
    assert resp_editor.status_code == 200
    assert "Critical Recruitment Fields" in resp_editor.text


def test_contradictory_critical_fact_blocks_normal_approval(editorial_env):
    """Contradictory critical fact blocks normal approval until resolved or confirmed."""
    client, db_file = editorial_env

    # Set total_vacancies to CONTRADICTORY
    with get_db(db_file) as conn:
        conn.execute("UPDATE extracted_facts SET verified_status = 'CONTRADICTORY', is_confirmed = 0 WHERE id = 'fact_wf_vac'")
        v1 = conn.execute("SELECT content_hash FROM article_versions WHERE id = 'arv_wf_1'").fetchone()
        v1_hash = v1["content_hash"]

    # Attempt normal approval
    resp = client.post(
        "/api/editorial/articles/art_wf_1/decide",
        json={
            "expected_version_id": "arv_wf_1",
            "expected_content_hash": v1_hash,
            "decision": "APPROVE",
            "editor_email": "meettomar07@gmail.com",
            "is_override": False,
        },
    )
    assert resp.status_code == 400
    assert "Normal approval is BLOCKED" in resp.json()["detail"]
    assert "Critical facts are unverified: total_vacancies" in resp.json()["detail"]

    # Now confirm the fact
    resp_conf = client.post(
        "/api/editorial/facts/fact_wf_vac/confirm",
        json={"reviewer_email": "meettomar07@gmail.com"},
    )
    assert resp_conf.status_code == 200

    # Normal approval should now succeed
    resp_appr = client.post(
        "/api/editorial/articles/art_wf_1/decide",
        json={
            "expected_version_id": "arv_wf_1",
            "expected_content_hash": v1_hash,
            "decision": "APPROVE",
            "editor_email": "meettomar07@gmail.com",
            "is_override": False,
        },
    )
    assert resp_appr.status_code == 200
    assert resp_appr.json()["decision"] == "APPROVED"
