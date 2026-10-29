"""Automated regression and acceptance tests for the Local Editorial Review Interface."""

import hashlib
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.api.app import app
from testkart_intelligence.config import settings
from testkart_intelligence.publishing.guard import (
    assert_live_publishing_disabled,
    LivePublishingDisabledError,
)


@pytest.fixture
def test_setup(tmp_path: Path, monkeypatch):
    """Set up isolated test database with realistic test notices, versions, facts, and drafts."""
    db_file = tmp_path / "editorial_test.db"
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    monkeypatch.setattr(settings, "DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path)

    init_db(db_file)
    with get_db(db_file) as conn:
        seed_sources_if_empty(conn)

        # 1. Official PDF file on disk
        pdf_path = docs_dir / "upsc_geo_2026.pdf"
        pdf_path.write_text("%PDF-1.4 official notice mock text", encoding="utf-8")

        # 2. Canonical notice (Clean, readable)
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_upsc_geo', 'src_upsc', 'Union Public Service Commission', '02/2026-GEOL',
                'Combined Geo-Scientist Examination 2026', 'https://upsc.gov.in/geo-2026.pdf',
                'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
                '2026-10-24T06:00:00Z', '2026-10-24T06:00:00Z'
            )
            """
        )

        doc_hash = hashlib.sha256(b"mock pdf bytes").hexdigest()
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES (
                'nver_geo_1', 'not_upsc_geo', 1, 'https://upsc.gov.in/geo-2026.pdf', ?,
                'PDF', ?, 'Official notification raw text with 85 vacancies', 5, '2026-10-24T06:00:00Z'
            )
            """,
            (doc_hash, str(pdf_path)),
        )

        # Extracted facts (including critical recruitment facts)
        facts = [
            ("recruiting_authority", "Union Public Service Commission", "VERIFIED", "Union Public Service Commission", 1),
            ("official_source_url", "https://upsc.gov.in/geo-2026.pdf", "VERIFIED", "https://upsc.gov.in/geo-2026.pdf", 1),
            ("total_vacancies", "85", "VERIFIED", "There are 85 vacancies in total across categories", 2),
            ("application_start_date", "15/11/2026", "VERIFIED", "Online applications open on 15/11/2026", 1),
            ("application_end_date", "15/12/2026", "VERIFIED", "Closing date for online submission is 15/12/2026", 1),
            ("exam_date", "18/02/2027", "VERIFIED", "Preliminary Examination will be held on 18/02/2027", 3),
        ]
        for idx, (k, val, st, ev, pg) in enumerate(facts):
            conn.execute(
                """
                INSERT INTO extracted_facts (
                    id, notice_version_id, fact_key, fact_value, confidence,
                    evidence_text, page_number, verified_status, created_at
                ) VALUES (?, 'nver_geo_1', ?, ?, 1.0, ?, ?, ?, '2026-10-24T06:00:00Z')
                """,
                (f"fact_{idx}", k, val, ev, pg, st),
            )

        # Article draft & version 1
        md_content = (
            "# Union Public Service Commission Combined Geo-Scientist Examination 2026\n\n"
            "Union Public Service Commission has announced recruitment for Combined Geo-Scientist Examination 2026.\n\n"
            "| Detail | Official Information |\n"
            "|---|---|\n"
            "| Recruiting Authority | Union Public Service Commission |\n"
            "| Total Vacancies | 85 |\n"
            "| Application Window | 15/11/2026 to 15/12/2026 |\n"
            "| Official Notification | [Download Notification](https://upsc.gov.in/geo-2026.pdf) |\n\n"
            "Interested candidates must apply online through the official portal."
        )
        content_hash = hashlib.sha256(md_content.encode("utf-8")).hexdigest()

        conn.execute(
            """
            INSERT INTO blog_articles (
                id, canonical_notice_id, template_type, current_version_id,
                status, title, slug, created_at, updated_at
            ) VALUES (
                'art_geo_2026', 'not_upsc_geo', 'recruitment.md.j2', 'arv_geo_1',
                'QA_PASSED', 'UPSC Combined Geo-Scientist 2026 Notification Out for 85 Posts',
                'upsc-geo-scientist-2026', '2026-10-24T06:10:00Z', '2026-10-24T06:10:00Z'
            )
            """
        )

        conn.execute(
            """
            INSERT INTO article_versions (
                id, article_id, version_number, content_markdown, content_hash,
                title, generated_by, created_at
            ) VALUES (
                'arv_geo_1', 'art_geo_2026', 1, ?, ?,
                'UPSC Combined Geo-Scientist 2026 Notification Out for 85 Posts',
                'agent_writer', '2026-10-24T06:10:00Z'
            )
            """,
            (md_content, content_hash),
        )

        # Passing QA checks
        conn.execute(
            """
            INSERT INTO qa_results (
                id, article_version_id, passed, score, rule_name, severity, message, created_at
            ) VALUES ('qa_1', 'arv_geo_1', 1, 100.0, 'rule_document_readability', 'ERROR', 'Document is clean', '2026-10-24T06:10:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO qa_results (
                id, article_version_id, passed, score, rule_name, severity, message, created_at
            ) VALUES ('qa_2', 'arv_geo_1', 1, 100.0, 'rule_recruitment_critical_dates', 'ERROR', 'Verified application dates found', '2026-10-24T06:10:00Z')
            """
        )

        # 3. Blocked scanned notice
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_scanned_bpsc', 'src_bpsc', 'Bihar Public Service Commission', '69/2026',
                'Assistant Professor Scanned Circular', 'https://bpsc.bih.nic.in/scan.pdf',
                'State', 'Bihar', 'RECRUITMENT_NOTIFICATION', 'SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW',
                '2026-10-24T07:00:00Z', '2026-10-24T07:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, page_count, retrieved_at
            ) VALUES (
                'nver_bpsc_1', 'not_scanned_bpsc', 1, 'https://bpsc.bih.nic.in/scan.pdf',
                'hash_bpsc_scanned', 'PDF', '/tmp/nonexistent.pdf', 3, '2026-10-24T07:00:00Z'
            )
            """
        )

        # Article for scanned notice with QA failure
        scanned_md = "# Scanned Notice Draft Without Verified Dates"
        scanned_hash = hashlib.sha256(scanned_md.encode("utf-8")).hexdigest()
        conn.execute(
            """
            INSERT INTO blog_articles (
                id, canonical_notice_id, template_type, current_version_id,
                status, title, slug, created_at, updated_at
            ) VALUES (
                'art_scanned_bpsc', 'not_scanned_bpsc', 'recruitment.md.j2', 'arv_scanned_1',
                'QA_FAILED', 'BPSC Assistant Professor Notice',
                'bpsc-assistant-prof', '2026-10-24T07:10:00Z', '2026-10-24T07:10:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO article_versions (
                id, article_id, version_number, content_markdown, content_hash,
                title, generated_by, created_at
            ) VALUES (
                'arv_scanned_1', 'art_scanned_bpsc', 1, ?, ?,
                'BPSC Assistant Professor Notice', 'agent_writer', '2026-10-24T07:10:00Z'
            )
            """,
            (scanned_md, scanned_hash),
        )
        conn.execute(
            """
            INSERT INTO qa_results (
                id, article_version_id, passed, score, rule_name, severity, message, created_at
            ) VALUES ('qa_scanned_1', 'arv_scanned_1', 0, 0.0, 'rule_document_readability', 'ERROR', 'Document is scanned (<50 chars/page)', '2026-10-24T07:10:00Z')
            """
        )

    return TestClient(app)


# --- 1. Dashboard Views & Filtering ---

def test_editorial_dashboard_overview_and_tabs(test_setup: TestClient):
    """Verify that the dashboard overview and all tabbed views render cleanly."""
    client = test_setup

    # Main dashboard
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Testkart Intelligence" in resp.text
    assert "LOCAL DEVELOPMENT ONLY" in resp.text
    assert "LIVE PUBLISHING DISABLED" in resp.text
    assert "Drafts Awaiting Human Review" in resp.text
    assert "Blocked Documents &amp; Critical Extraction Failures" in resp.text

    # Newly Discovered notices view
    resp_new = client.get("/editorial/notices?view=new")
    assert resp_new.status_code == 200
    assert "Official Notices Catalog" in resp_new.text
    assert "Combined Geo-Scientist" in resp_new.text

    # Blocked notices view
    resp_blocked = client.get("/editorial/notices?view=blocked")
    assert resp_blocked.status_code == 200
    assert "Assistant Professor Scanned Circular" in resp_blocked.text

    # Drafts awaiting review view
    resp_drafts = client.get("/editorial/articles?view=awaiting")
    assert resp_drafts.status_code == 200
    assert "UPSC Combined Geo-Scientist" in resp_drafts.text

    # Scan health & monitoring view
    resp_scans = client.get("/editorial/scans")
    assert resp_scans.status_code == 200
    assert "Official Government Portals Health" in resp_scans.text
    assert "UPSC" in resp_scans.text


# --- 2. Notice & Evidence Review ---

def test_notice_and_evidence_review(test_setup: TestClient):
    """Verify notice detail page displays official document links, hashes, and evidence excerpts."""
    client = test_setup
    resp = client.get("/editorial/notices/not_upsc_geo")
    assert resp.status_code == 200
    assert "Combined Geo-Scientist Examination 2026" in resp.text
    assert "https://upsc.gov.in/geo-2026.pdf" in resp.text
    assert "total_vacancies" in resp.text
    assert "85" in resp.text
    assert "15/11/2026" in resp.text
    assert "There are 85 vacancies in total across categories" in resp.text
    assert "Page 2" in resp.text
    assert "Download Local Verified PDF" in resp.text


# --- 3. Safe Document Download & Path Traversal Guard ---

def test_safe_document_download_and_path_traversal(test_setup: TestClient):
    """Verify safe document streaming from local storage and rejection of invalid/path-traversal requests."""
    client = test_setup

    # Valid local document download
    resp = client.get("/editorial/documents/nver_geo_1/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "%PDF-1.4 official notice mock text" in resp.text

    # Nonexistent or invalid document
    resp_invalid = client.get("/editorial/documents/nver_invalid_id/download")
    assert resp_invalid.status_code == 404

    # Document outside allowed directory
    resp_blocked = client.get("/editorial/documents/nver_bpsc_1/download")
    assert resp_blocked.status_code == 404


# --- 4. Draft Editing & Prior Approval Invalidation ---

def test_draft_editing_creates_new_version_and_invalidates_approval(test_setup: TestClient):
    """Editing an article draft must create version N+1, tag editor author, and reset approvals."""
    client = test_setup

    # 1. First approve v1
    resp_appr = client.post(
        "/api/editorial/articles/art_geo_2026/decide",
        json={
            "expected_version_id": "arv_geo_1",
            "expected_content_hash": hashlib.sha256(
                client.get("/editorial/articles/art_geo_2026").text.encode("utf-8")
            ).hexdigest(),  # Will fetch exact hash below
            "decision": "APPROVE",
            "editor_email": "meettomar07@gmail.com",
        },
    )

    with get_db() as conn:
        v1 = conn.execute("SELECT content_hash FROM article_versions WHERE id = 'arv_geo_1'").fetchone()
        v1_hash = v1["content_hash"]

    # Submit clean approval for v1
    resp_appr = client.post(
        "/api/editorial/articles/art_geo_2026/decide",
        json={
            "expected_version_id": "arv_geo_1",
            "expected_content_hash": v1_hash,
            "decision": "APPROVE",
            "editor_email": "meettomar07@gmail.com",
        },
    )
    assert resp_appr.status_code == 200
    assert resp_appr.json()["decision"] == "APPROVED"

    # Confirm article is APPROVED in DB
    with get_db() as conn:
        art = conn.execute("SELECT status FROM blog_articles WHERE id = 'art_geo_2026'").fetchone()
        assert art["status"] == "APPROVED"
        appr_rec = conn.execute("SELECT status FROM approval_records WHERE article_version_id = 'arv_geo_1'").fetchone()
        assert appr_rec["status"] == "APPROVED"

    # 2. Now edit the draft
    edited_md = (
        "# UPSC Combined Geo-Scientist Examination 2026 (Updated by Editor)\n\n"
        "Editor verified and expanded the application guidelines.\n\n"
        "| Field | Value |\n|---|---|\n| Vacancies | 85 |\n| Start Date | 15/11/2026 |\n| End Date | 15/12/2026 |\n"
    )
    resp_save = client.post(
        "/api/editorial/articles/art_geo_2026/save",
        json={
            "expected_version_id": "arv_geo_1",
            "title": "UPSC Combined Geo-Scientist 2026 Notification Out (85 Posts)",
            "content_markdown": edited_md,
            "editor_email": "meettomar07@gmail.com",
        },
    )
    assert resp_save.status_code == 200
    data = resp_save.json()
    assert data["version_number"] == 2
    assert data["generated_by"] == "human_editor:meettomar07@gmail.com"
    new_v_id = data["version_id"]

    # 3. Verify prior approval record is now INVALIDATED and article status is DRAFT/QA_PASSED
    with get_db() as conn:
        art_after = conn.execute("SELECT status, current_version_id FROM blog_articles WHERE id = 'art_geo_2026'").fetchone()
        assert art_after["current_version_id"] == new_v_id

        # Prior approval MUST be INVALIDATED
        old_appr = conn.execute("SELECT status FROM approval_records WHERE article_version_id = 'arv_geo_1'").fetchone()
        assert old_appr["status"] == "INVALIDATED"


# --- 5. Stale Version Approval Rejection (Concurrency Conflict) ---

def test_stale_version_approval_rejection(test_setup: TestClient):
    """Attempting to approve or edit with an outdated version ID or mismatched hash must return 409 Conflict."""
    client = test_setup

    with get_db() as conn:
        v1 = conn.execute("SELECT content_hash FROM article_versions WHERE id = 'arv_geo_1'").fetchone()
        v1_hash = v1["content_hash"]

    # 1. Submit edit to advance article to version 2
    client.post(
        "/api/editorial/articles/art_geo_2026/save",
        json={
            "expected_version_id": "arv_geo_1",
            "title": "UPSC Geo-Scientist 2026 (v2)",
            "content_markdown": "# Version 2 Content\n\nUpdated text for version 2.",
            "editor_email": "meettomar07@gmail.com",
        },
    )

    # 2. Simulate a stale browser tab trying to approve version 1
    resp_stale_approve = client.post(
        "/api/editorial/articles/art_geo_2026/decide",
        json={
            "expected_version_id": "arv_geo_1",  # STALE: current active is v2
            "expected_content_hash": v1_hash,
            "decision": "APPROVE",
            "editor_email": "meettomar07@gmail.com",
        },
    )
    assert resp_stale_approve.status_code == 409
    assert "Stale version conflict" in resp_stale_approve.json()["detail"]

    # 3. Simulate a stale tab trying to save against version 1
    resp_stale_save = client.post(
        "/api/editorial/articles/art_geo_2026/save",
        json={
            "expected_version_id": "arv_geo_1",  # STALE
            "title": "UPSC Stale Edit",
            "content_markdown": "# Stale edit content",
            "editor_email": "meettomar07@gmail.com",
        },
    )
    assert resp_stale_save.status_code == 409
    assert "Conflict" in resp_stale_save.json()["detail"]


# --- 6. Scanned Document Approval Blocked Without Override ---

def test_scanned_document_blocks_normal_approval(test_setup: TestClient):
    """A draft based on a scanned/unreadable document must block normal approval."""
    client = test_setup

    with get_db() as conn:
        v = conn.execute("SELECT content_hash FROM article_versions WHERE id = 'arv_scanned_1'").fetchone()
        scanned_hash = v["content_hash"]

    # Attempt normal approval
    resp = client.post(
        "/api/editorial/articles/art_scanned_bpsc/decide",
        json={
            "expected_version_id": "arv_scanned_1",
            "expected_content_hash": scanned_hash,
            "decision": "APPROVE",
            "editor_email": "meettomar07@gmail.com",
            "is_override": False,
        },
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "Normal approval is BLOCKED" in detail
    assert "unreadable or flagged" in detail


# --- 7. Unverified Critical Facts Block Normal Approval ---

def test_unverified_critical_facts_block_normal_approval(test_setup: TestClient):
    """A recruitment draft lacking verified opening/closing dates or vacancies must block normal approval."""
    client = test_setup

    # Remove application start date from database to simulate unverified fact
    with get_db() as conn:
        conn.execute("DELETE FROM extracted_facts WHERE fact_key = 'application_start_date'")
        v1 = conn.execute("SELECT content_hash FROM article_versions WHERE id = 'arv_geo_1'").fetchone()
        v1_hash = v1["content_hash"]

    # Attempt normal approval
    resp = client.post(
        "/api/editorial/articles/art_geo_2026/decide",
        json={
            "expected_version_id": "arv_geo_1",
            "expected_content_hash": v1_hash,
            "decision": "APPROVE",
            "editor_email": "meettomar07@gmail.com",
            "is_override": False,
        },
    )
    assert resp.status_code == 400
    assert "Critical facts are unverified: application_start_date" in resp.json()["detail"]


# --- 8. Audited Editorial Override Workflow & Invariant Preservation ---

def test_audited_editorial_override_records_justification_and_preserves_guard(test_setup: TestClient):
    """An explicit editorial override must record responsible editor, mandatory reason, and keep live publishing disabled."""
    client = test_setup

    with get_db() as conn:
        v = conn.execute("SELECT content_hash FROM article_versions WHERE id = 'arv_scanned_1'").fetchone()
        scanned_hash = v["content_hash"]

    # 1. Attempt override with missing/short reason (< 10 chars)
    resp_short = client.post(
        "/api/editorial/articles/art_scanned_bpsc/decide",
        json={
            "expected_version_id": "arv_scanned_1",
            "expected_content_hash": scanned_hash,
            "decision": "APPROVE",
            "editor_email": "meettomar07@gmail.com",
            "is_override": True,
            "override_reason": "too short",  # Too short (9 chars < 10)
        },
    )
    assert resp_short.status_code == 400
    assert "minimum 10 characters" in resp_short.json()["detail"]

    # 2. Submit valid audited override
    override_reason = "Manually inspected scanned circular page 1: verified 45 assistant professor posts and deadline 20/12/2026."
    resp_valid = client.post(
        "/api/editorial/articles/art_scanned_bpsc/decide",
        json={
            "expected_version_id": "arv_scanned_1",
            "expected_content_hash": scanned_hash,
            "decision": "APPROVE",
            "editor_email": "meettomar07@gmail.com",
            "is_override": True,
            "override_reason": override_reason,
            "notes": "Verified in high-res offline viewer.",
        },
    )
    assert resp_valid.status_code == 200
    data = resp_valid.json()
    assert data["decision"] == "APPROVED"
    assert data["is_override"] is True
    assert data["live_publishing_enabled"] is False  # Guard intact!

    # 3. Verify audit log integrity in database
    with get_db() as conn:
        art = conn.execute("SELECT status FROM blog_articles WHERE id = 'art_scanned_bpsc'").fetchone()
        assert art["status"] == "APPROVED"

        appr = conn.execute(
            "SELECT * FROM approval_records WHERE article_version_id = 'arv_scanned_1' AND status = 'APPROVED'"
        ).fetchone()
        assert appr is not None
        assert "EDITORIAL_OVERRIDE" in appr["decision_notes"]
        assert override_reason in appr["decision_notes"]
        assert appr["reviewer_email"] == "meettomar07@gmail.com"

        audit_ev = conn.execute(
            "SELECT * FROM audit_events WHERE action = 'EDITORIAL_OVERRIDE_APPROVED' ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        assert audit_ev is not None
        assert audit_ev["actor"] == "meettomar07@gmail.com"
        payload = json.loads(audit_ev["payload_json"])
        assert payload["is_override"] is True
        assert payload["live_publishing_enabled"] is False


# --- 9. Rejection & Correction Request Workflows ---

def test_rejection_and_correction_request_workflows(test_setup: TestClient):
    """Verify rejection and correction request state changes and audit events."""
    client = test_setup

    with get_db() as conn:
        v1 = conn.execute("SELECT content_hash FROM article_versions WHERE id = 'arv_geo_1'").fetchone()
        v1_hash = v1["content_hash"]

    # 1. Request correction
    resp_corr = client.post(
        "/api/editorial/articles/art_geo_2026/decide",
        json={
            "expected_version_id": "arv_geo_1",
            "expected_content_hash": v1_hash,
            "decision": "REQUEST_CORRECTION",
            "editor_email": "meettomar07@gmail.com",
            "notes": "Please expand eligibility criteria for hydrogeology post.",
        },
    )
    assert resp_corr.status_code == 200
    assert resp_corr.json()["decision"] == "CORRECTION_REQUESTED"

    with get_db() as conn:
        art = conn.execute("SELECT status FROM blog_articles WHERE id = 'art_geo_2026'").fetchone()
        assert art["status"] == "CORRECTION_REQUESTED"

    # 2. Reject draft
    resp_rej = client.post(
        "/api/editorial/articles/art_geo_2026/decide",
        json={
            "expected_version_id": "arv_geo_1",
            "expected_content_hash": v1_hash,
            "decision": "REJECT",
            "editor_email": "meettomar07@gmail.com",
            "notes": "Exam was cancelled by subsequent corrigendum.",
        },
    )
    assert resp_rej.status_code == 200
    assert resp_rej.json()["decision"] == "REJECTED"

    with get_db() as conn:
        art = conn.execute("SELECT status FROM blog_articles WHERE id = 'art_geo_2026'").fetchone()
        assert art["status"] == "REJECTED"
        rej_record = conn.execute("SELECT * FROM approval_records WHERE status = 'REJECTED'").fetchone()
        assert rej_record is not None
        assert "cancelled by subsequent corrigendum" in rej_record["decision_notes"]


# --- 10. XSS Prevention & Unsafe HTML Sanitization ---

def test_xss_and_unsafe_html_handling(test_setup: TestClient):
    """Verify that malicious script tags, onerror handlers, and javascript: links are escaped and neutralized."""
    client = test_setup

    malicious_md = (
        "# Malicious Notice <script>alert('xss')</script>\n\n"
        "<img src=x onerror=alert('steal_cookie')>\n\n"
        "[Click For Free Jobs](javascript:alert('pwned'))\n\n"
        "<iframe src='http://evil.com'></iframe>\n\n"
        "Safe text here."
    )

    resp = client.post(
        "/api/editorial/articles/art_geo_2026/preview",
        json={"content_markdown": malicious_md},
    )
    assert resp.status_code == 200
    html_output = resp.json()["rendered_html"]

    # Verify no raw script tags or evil attributes executed
    assert "<script>" not in html_output
    assert "&lt;script&gt;" in html_output
    assert "onerror=" not in html_output
    assert "&lt;img" in html_output
    assert "<iframe" not in html_output
    assert 'href="javascript:' not in html_output


# --- 11. Localhost Only Service Binding & Unauthorized Host Rejection ---

def test_localhost_only_service_binding_and_unauthorized_host(test_setup: TestClient):
    """Verify that Settings binds to 127.0.0.1 and requests with untrusted external hosts/origins are blocked."""
    assert settings.SERVER_HOST == "127.0.0.1"
    client = test_setup

    # Authorized local host requests succeed
    resp_local = client.get("/", headers={"host": "127.0.0.1:8000"})
    assert resp_local.status_code == 200

    # Unauthorized remote host header must be rejected
    resp_remote = client.get("/", headers={"host": "external-attacker-site.com"})
    assert resp_remote.status_code == 403
    assert "Forbidden" in resp_remote.json()["detail"]

    # Unauthorized Origin on state-changing request must be rejected
    resp_bad_origin = client.post(
        "/api/editorial/articles/art_geo_2026/preview",
        headers={"origin": "http://malicious-site.com"},
        json={"content_markdown": "# Test"},
    )
    assert resp_bad_origin.status_code == 403


# --- 12. Permanent Prohibition on Live Publishing ---

def test_live_publishing_remains_strictly_disabled_across_editorial(test_setup: TestClient, monkeypatch):
    """Verify that ALLOW_LIVE_PUBLISHING = False is unyielding across all editorial workflows."""
    assert settings.ALLOW_LIVE_PUBLISHING is False
    assert_live_publishing_disabled()

    # Attempting to tamper with the flag triggers LivePublishingDisabledError
    monkeypatch.setattr(settings, "ALLOW_LIVE_PUBLISHING", True)
    with pytest.raises(LivePublishingDisabledError):
        assert_live_publishing_disabled()


# --- 13. Local Server Startup and HTTP Response Verification ---

def test_local_server_startup_and_http_response():
    """Verify that the CLI serve command initializes Uvicorn, binds to 127.0.0.1:8000, and returns 200 OK."""
    import subprocess
    import sys
    import time
    import urllib.request
    import json

    proc = subprocess.Popen(
        [sys.executable, "-m", "testkart_intelligence.cli", "serve"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        responded = False
        dashboard_html = ""
        status_data = {}
        # Wait up to 10 seconds for the server to bind and respond
        for _ in range(40):
            time.sleep(0.25)
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=1.5) as resp:
                    if resp.status == 200:
                        dashboard_html = resp.read().decode("utf-8")
                        responded = True
                        break
            except Exception:
                continue

        assert responded is True, f"Server failed to start or respond. Stderr: {proc.stderr.read().decode(errors='replace')}"
        assert "Testkart Intelligence" in dashboard_html
        assert "LIVE PUBLISHING DISABLED" in dashboard_html

        # Verify status API endpoint
        with urllib.request.urlopen("http://127.0.0.1:8000/api/status", timeout=1.5) as resp:
            assert resp.status == 200
            status_data = json.loads(resp.read().decode("utf-8"))
            assert status_data["live_publishing_enabled"] is False

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
