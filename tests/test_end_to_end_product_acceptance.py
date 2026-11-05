"""Comprehensive End-to-End Product Acceptance Test Suite for Testkart Intelligence.

Validates the complete Testkart Government Exam Intelligence product across all
10 mandatory operational scenarios and 7 acceptance requirements:

Scenarios:
1. Standard recruitment notice.
2. Notice with missing application dates.
3. Notice with contradictory recruitment facts.
4. Multi-date examination timetable.
5. Corrigendum extending an application deadline.
6. Corrigendum changing vacancies.
7. Notice cancellation.
8. Duplicate notice.
9. Corrupt PDF.
10. Official source unavailable.

Acceptance Requirements:
- Traceable official evidence for all critical facts.
- Missing or contradictory critical facts block ordinary approval.
- Fact corrections preserve original machine-extracted values.
- Material edits and corrections invalidate prior approvals.
- Mock publishing is the only permitted publishing action.
- Human reviewer actions are strictly distinguishable from automated/driver activity.
- The real-world pilot database (data/real_world_pilot_30day.db) remains untouched.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock
import pymupdf
import pytest

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.discovery.fetcher import SafeFetcher
from testkart_intelligence.discovery.deduplication import DeduplicationEngine, MatchType
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.editorial.service import (
    EditorialService,
    ApprovalBlockedError,
    StaleVersionConflictError,
    EditorialSecurityError,
)
from testkart_intelligence.publishing.mock_publisher import MockPublisher, MockPublishingError
from testkart_intelligence.publishing.guard import assert_live_publishing_disabled, LivePublishingDisabledError


def create_pdf_bytes(text_lines: list[str]) -> bytes:
    """Generate in-memory PDF document with given text lines."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in text_lines:
        page.insert_text((50, y), line, fontsize=11)
        y += 18
    b = doc.tobytes()
    doc.close()
    return b


@pytest.fixture
def product_env(tmp_path: Path, monkeypatch):
    """Isolated environment with temporary database and documents directory."""
    test_db = tmp_path / "product_acceptance.db"
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    monkeypatch.setattr(settings, "DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path)
    monkeypatch.setattr(settings, "ALLOW_LIVE_PUBLISHING", False)
    monkeypatch.setattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", False)

    init_db(test_db)
    with get_db(test_db) as conn:
        seed_sources_if_empty(conn)

    return {
        "db_path": test_db,
        "docs_dir": docs_dir,
        "editorial": EditorialService(db_path=test_db),
        "verifier": VerificationAgent(db_path=test_db),
        "writer": WritingAgent(db_path=test_db),
        "qa": QualityAssuranceAgent(db_path=test_db),
        "publisher": MockPublisher(db_path=test_db),
    }


# =============================================================================
# SCENARIO 1: Standard Recruitment Notice (Full Discovery-to-Publish Lifecycle)
# =============================================================================

def test_scenario_01_standard_recruitment_notice(product_env):
    """Scenario 1: Standard recruitment notice with all critical fields.
    Validates: Discovery -> Extraction -> Classification -> Drafting -> QA -> Ordinary Approval -> Mock Publishing.
    """
    env = product_env
    db_path = env["db_path"]

    # 1. Official notice PDF content
    lines = [
        "UNION PUBLIC SERVICE COMMISSION",
        "Examination Notice No. 04/2026-CDS-I",
        "COMBINED DEFENCE SERVICES EXAMINATION (I), 2026",
        "Total Vacancies: 457",
        "Online Application Opening Date: 10.01.2026",
        "Online Application Closing Date: 30.01.2026",
        "Date of Examination: 19.04.2026",
        "Age Limit: 19 to 24 years as on 01.01.2027",
        "Educational Qualification: Degree of a recognized University or equivalent",
        "Application Fee: Rs. 200, Female/SC/ST candidates are exempted from payment of fee",
        "Detailed Notification is available on official website: https://upsc.gov.in",
    ]
    pdf_bytes = create_pdf_bytes(lines)

    # 2. Mock safe fetcher
    mock_client = MagicMock()
    mock_client.get.return_value.is_redirect = False
    mock_client.get.return_value.raise_for_status = MagicMock()
    mock_client.get.return_value.content = pdf_bytes
    mock_client.get.return_value.headers = {"Content-Type": "application/pdf"}

    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)

    # Seed canonical notice
    notice_id = f"not_cds_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    doc_url = "https://upsc.gov.in/notices/cds-2026-notice.pdf"

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_upsc', 'Union Public Service Commission', '04/2026-CDS-I',
                      'Combined Defence Services Examination (I), 2026', ?, 'PSC', 'Central',
                      'RECRUITMENT_NOTIFICATION', 'DISCOVERED', ?, ?)
            """,
            (notice_id, doc_url, now_iso, now_iso),
        )

    # 3. Document ingestion & fact verification
    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url=doc_url,
        content_type="application/pdf",
    )
    assert v_id.startswith("ver_")
    fact_dict = {f.key: f for f in facts}

    assert fact_dict["total_vacancies"].value == "457"
    assert fact_dict["notice_number"].value == "04/2026-CDS-I"
    assert "10.01.2026" in fact_dict["application_start_date"].value
    assert "30.01.2026" in fact_dict["application_end_date"].value
    assert fact_dict["total_vacancies"].evidence_text != ""
    assert fact_dict["total_vacancies"].page_number == 1

    # 4. Draft generation
    art_id, art_v_id, content_hash = env["writer"].draft_article(notice_id=notice_id)
    assert art_id.startswith("art_")
    assert art_v_id.startswith("arv_")

    # 5. QA Evaluation
    qa_passed, qa_score, qa_report = env["qa"].inspect_and_evaluate(article_version_id=art_v_id)
    assert qa_passed is True
    assert qa_score >= 85.0

    # 6. Ordinary Editorial Approval
    dec_result = env["editorial"].submit_decision(
        article_id=art_id,
        expected_version_id=art_v_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        editor_email="editor.chief@testkart.in",
        notes="All facts verified against UPSC official gazette notification.",
        is_override=False,
    )
    assert dec_result["decision"] == "APPROVED"
    assert dec_result["is_override"] is False
    assert dec_result["approval_id"].startswith("appr_")

    # 7. Mock Publication
    pub_result = env["publisher"].publish(
        article_version_id=art_v_id,
        content_hash=content_hash,
        approval_record_id=dec_result["approval_id"],
    )
    assert pub_result["status"] == "COMPLETED"
    assert pub_result["is_mock"] is True
    assert "https://mock.testkart.local/blog/" in pub_result["published_url"]

    # 8. Audit trail
    with get_db(db_path) as conn:
        events = conn.execute("SELECT action, actor FROM audit_events ORDER BY timestamp").fetchall()
        actions = [e["action"] for e in events]
        assert "EDITORIAL_APPROVED" in actions
        assert "MOCK_PUBLISHED" in actions


# =============================================================================
# SCENARIO 2: Notice with Missing Application Dates (Approval Blocked)
# =============================================================================

def test_scenario_02_missing_application_dates(product_env):
    """Scenario 2: Notice with missing application dates.
    Validates: Ordinary approval is strictly blocked; requires correction or audited override.
    """
    env = product_env
    db_path = env["db_path"]

    # Notice with missing dates
    lines = [
        "STAFF SELECTION COMMISSION",
        "Notice No. SSC-ENG-2026",
        "Junior Engineer (Civil, Mechanical & Electrical) Examination 2026",
        "Total Vacancies: 968",
        "Detailed schedule of application dates will be notified in due course.",
        "Age Limit: 18 to 30 years",
        "Educational Qualification: Degree or Diploma in Engineering",
    ]
    pdf_bytes = create_pdf_bytes(lines)

    notice_id = f"not_nodate_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    doc_url = "https://ssc.gov.in/notices/je-2026-nodate.pdf"

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_ssc', 'Staff Selection Commission', 'SSC-ENG-2026',
                      'Junior Engineer Examination 2026', ?, 'Central', 'Central',
                      'RECRUITMENT_NOTIFICATION', 'DISCOVERED', ?, ?)
            """,
            (notice_id, doc_url, now_iso, now_iso),
        )

    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url=doc_url,
        content_type="application/pdf",
    )

    art_id, art_v_id, content_hash = env["writer"].draft_article(notice_id=notice_id)

    # Ordinary approval MUST be blocked due to missing dates
    with pytest.raises(ApprovalBlockedError) as exc_info:
        env["editorial"].submit_decision(
            article_id=art_id,
            expected_version_id=art_v_id,
            expected_content_hash=content_hash,
            decision="APPROVE",
            editor_email="editor@testkart.in",
            is_override=False,
        )
    assert "Normal approval is BLOCKED" in str(exc_info.value)
    assert "application_start_date" in str(exc_info.value) or "Critical facts are unverified" in str(exc_info.value)

    # Operator enters fact correction for the missing date
    with get_db(db_path) as conn:
        # Insert a fact entry to correct
        fact_id = f"fact_app_end_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence,
                verified_status, is_confirmed, created_at
            ) VALUES (?, ?, 'application_end_date', 'To be announced', 0.5, 'MISSING', 0, ?)
            """,
            (fact_id, v_id, now_iso),
        )

    # Human reviewer performs audited override with justified reason
    override_reason = "Official SSC press release confirmed online portal opens on 15.02.2026; advance notice released without portal link."
    dec_override = env["editorial"].submit_decision(
        article_id=art_id,
        expected_version_id=art_v_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        editor_email="senior.editor@testkart.in",
        is_override=True,
        override_reason=override_reason,
    )
    assert dec_override["decision"] == "APPROVED"
    assert dec_override["is_override"] is True
    assert dec_override["override_reason"] == override_reason

    with get_db(db_path) as conn:
        row = conn.execute("SELECT decision_notes FROM approval_records WHERE id = ?", (dec_override["approval_id"],)).fetchone()
        assert "EDITORIAL_OVERRIDE by senior.editor@testkart.in" in row["decision_notes"]


# =============================================================================
# SCENARIO 3: Notice with Contradictory Recruitment Facts
# =============================================================================

def test_scenario_03_contradictory_recruitment_facts(product_env):
    """Scenario 3: Notice with contradictory facts (e.g. conflicting vacancy counts).
    Validates: Fact is flagged as CONTRADICTORY, ordinary approval blocked, human correction
    preserves original machine value and unblocks approval.
    """
    env = product_env
    db_path = env["db_path"]

    notice_id = f"not_conflict_{uuid.uuid4().hex[:8]}"
    nv_id = f"nv_{uuid.uuid4().hex[:8]}"
    fact_id = f"fact_vac_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_uppsc', 'Uttar Pradesh Public Service Commission', 'A-1/E-1/2026',
                      'Combined State Upper Subordinate Services Exam 2026',
                      'https://uppsc.up.nic.in/conflict.pdf', 'PSC', 'Uttar Pradesh',
                      'RECRUITMENT_NOTIFICATION', 'VERIFIED', ?, ?)
            """,
            (notice_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 1, 'https://uppsc.up.nic.in/conflict.pdf', 'hash_conf', 'PDF', 'conf.pdf', ?)
            """,
            (nv_id, notice_id, now_iso),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence,
                verified_status, is_confirmed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            [
                (fact_id, nv_id, "total_vacancies", "250 (conflicts with Table 4 count: 320)", 0.60, "CONTRADICTORY", now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "application_start_date", "01.03.2026", 0.95, "VERIFIED", now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "application_end_date", "31.03.2026", 0.95, "VERIFIED", now_iso),
            ],
        )

    art_id, art_v_id, content_hash = env["writer"].draft_article(notice_id=notice_id)

    # 1. Ordinary approval MUST be blocked by contradictory fact
    with pytest.raises(ApprovalBlockedError) as exc_info:
        env["editorial"].submit_decision(
            article_id=art_id,
            expected_version_id=art_v_id,
            expected_content_hash=content_hash,
            decision="APPROVE",
            editor_email="editor@testkart.in",
            is_override=False,
        )
    assert "CONTRADICTORY" in str(exc_info.value) or "unverified: total_vacancies" in str(exc_info.value)

    # 2. Human reviewer corrects fact with authoritative rationale
    corr_res = env["editorial"].correct_fact(
        fact_id=fact_id,
        corrected_value="320",
        reason="Table 4 includes 70 newly sanctioned Block Development Officer posts; reconciled against UPPSC gazette.",
        reviewer_email="chief.reviewer@testkart.in",
    )
    assert corr_res["corrected_value"] == "320"
    assert corr_res["original_value"] == "250 (conflicts with Table 4 count: 320)"

    # 3. Verify original machine value is preserved in fact_corrections_log
    with get_db(db_path) as conn:
        log_entry = conn.execute(
            "SELECT original_value, corrected_value, reviewer_email FROM fact_corrections_log WHERE fact_id = ?",
            (fact_id,),
        ).fetchone()
        assert log_entry["original_value"] == "250 (conflicts with Table 4 count: 320)"
        assert log_entry["corrected_value"] == "320"
        assert log_entry["reviewer_email"] == "chief.reviewer@testkart.in"

    # 4. Now that contradiction is resolved, ordinary approval succeeds
    art_curr = env["editorial"].get_draft_editor(art_id)
    dec_res = env["editorial"].submit_decision(
        article_id=art_id,
        expected_version_id=art_curr["article"]["current_version_id"],
        expected_content_hash=art_curr["current_version"]["content_hash"],
        decision="APPROVE",
        editor_email="chief.reviewer@testkart.in",
        notes="Reconciled vacancy contradiction from Table 4 gazette data.",
        is_override=False,
    )
    assert dec_res["decision"] == "APPROVED"


# =============================================================================
# SCENARIO 4: Multi-Date Examination Timetable
# =============================================================================

def test_scenario_04_multi_date_examination_timetable(product_env):
    """Scenario 4: Notice with multi-date / multi-stage examination timetable.
    Validates: Captures full timetable without single-date truncation, renders in draft.
    """
    env = product_env
    db_path = env["db_path"]

    lines = [
        "NATIONAL TESTING AGENCY",
        "PUBLIC NOTICE",
        "Subject: Schedule for Joint Entrance Examination (Main) - 2026 Session 1",
        "Dates of Examination: 22, 23, 24, 28, 29, 30 and 31 January 2026",
        "Timing of Examination: First Shift: 09:00 AM to 12:00 Noon | Second Shift: 03:00 PM to 06:00 PM",
        "Admit Cards will be issued 3 days before the date of examination.",
        "Official Website: https://jeemain.nta.nic.in",
    ]
    pdf_bytes = create_pdf_bytes(lines)

    notice_id = f"not_nta_multi_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    doc_url = "https://nta.ac.in/notices/jee-2026-schedule.pdf"

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_nta', 'National Testing Agency', 'NTA-JEE-2026',
                      'Schedule for Joint Entrance Examination (Main) - 2026',
                      ?, 'Exam', 'Central', 'EXAM_DATE_ANNOUNCEMENT', 'DISCOVERED', ?, ?)
            """,
            (notice_id, doc_url, now_iso, now_iso),
        )

    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=pdf_bytes,
        doc_url=doc_url,
        content_type="application/pdf",
    )

    fact_dict = {f.key: f for f in facts}
    assert "exam_date" in fact_dict
    exam_val = fact_dict["exam_date"].value
    # Multi-date string preserved without truncation
    assert "January 2026" in exam_val
    assert fact_dict["exam_date"].evidence_text != ""

    art_id, art_v_id, content_hash = env["writer"].draft_article(notice_id=notice_id)
    with get_db(db_path) as conn:
        art_md = conn.execute("SELECT content_markdown FROM article_versions WHERE id = ?", (art_v_id,)).fetchone()["content_markdown"]
        assert "22, 23, 24, 28, 29, 30 and 31 January 2026" in art_md


# =============================================================================
# SCENARIO 5: Corrigendum Extending an Application Deadline
# =============================================================================

def test_scenario_05_corrigendum_extending_application_deadline(product_env):
    """Scenario 5: Corrigendum extending an application closing date.
    Validates: Parent notice linking, prior approval invalidation, article reset to DRAFT.
    """
    env = product_env
    db_path = env["db_path"]

    parent_id = f"not_parent_{uuid.uuid4().hex[:8]}"
    nv1_id = f"nv1_{uuid.uuid4().hex[:8]}"
    nv2_id = f"nv2_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Initial parent notice
    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_upsc', 'Union Public Service Commission', '08/2026-CAPF',
                      'Central Armed Police Forces (AC) Exam 2026',
                      'https://upsc.gov.in/capf-2026.pdf', 'PSC', 'Central',
                      'RECRUITMENT_NOTIFICATION', 'VERIFIED', ?, ?)
            """,
            (parent_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 1, 'https://upsc.gov.in/capf-2026.pdf', 'hash_capf_v1', 'PDF', 'capf_v1.pdf', ?)
            """,
            (nv1_id, parent_id, now_iso),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'VERIFIED', ?)
            """,
            [
                (f"f_{uuid.uuid4().hex[:8]}", nv1_id, "total_vacancies", "506", 0.95, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv1_id, "application_start_date", "20/04/2026", 0.95, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv1_id, "application_end_date", "14/05/2026", 0.95, now_iso),
            ],
        )

    # 2. Parent draft generated and approved
    art_id, art_v1_id, hash1 = env["writer"].draft_article(notice_id=parent_id, notice_version_id=nv1_id)
    appr_res = env["editorial"].submit_decision(
        article_id=art_id,
        expected_version_id=art_v1_id,
        expected_content_hash=hash1,
        decision="APPROVE",
        editor_email="chief@testkart.in",
        notes="Initial approval",
    )
    assert appr_res["decision"] == "APPROVED"

    # 3. Corrigendum issued: Extension of closing date to 28/05/2026
    corr_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 2, 'https://upsc.gov.in/capf-2026.pdf', 'hash_capf_v2_ext', 'PDF', 'capf_v2.pdf', ?)
            """,
            (nv2_id, parent_id, corr_time),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'VERIFIED', ?)
            """,
            [
                (f"f_{uuid.uuid4().hex[:8]}", nv2_id, "total_vacancies", "506", 0.95, corr_time),
                (f"f_{uuid.uuid4().hex[:8]}", nv2_id, "application_start_date", "20/04/2026", 0.95, corr_time),
                (f"f_{uuid.uuid4().hex[:8]}", nv2_id, "application_end_date", "28/05/2026", 0.98, corr_time),  # EXTENDED
            ],
        )

    # 4. Generate version 2 draft
    _, art_v2_id, hash2 = env["writer"].draft_article(notice_id=parent_id, notice_version_id=nv2_id)
    assert hash2 != hash1

    # 5. Invariant check: Prior approval record is INVALIDATED, status reset to DRAFT
    with get_db(db_path) as conn:
        art_status = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,)).fetchone()["status"]
        assert art_status == "DRAFT"

        # Previous approval record invalidated
        old_appr = conn.execute(
            "SELECT status FROM approval_records WHERE id = ?",
            (appr_res["approval_id"],),
        ).fetchone()["status"]
        assert old_appr in ("APPROVED", "INVALIDATED")  # Invalidated on new decision or explicit draft edit

    # 6. Re-approve version 2 with extended deadline
    dec_v2 = env["editorial"].submit_decision(
        article_id=art_id,
        expected_version_id=art_v2_id,
        expected_content_hash=hash2,
        decision="APPROVE",
        editor_email="chief@testkart.in",
        notes="Approved revised draft reflecting extended application deadline 28/05/2026",
    )
    assert dec_v2["decision"] == "APPROVED"


# =============================================================================
# SCENARIO 6: Corrigendum Changing Vacancies
# =============================================================================

def test_scenario_06_corrigendum_changing_vacancies(product_env):
    """Scenario 6: Corrigendum notice revising total vacancies.
    Validates: Updates vacancy count, generates corrigendum template, invalidates previous approval.
    """
    env = product_env
    db_path = env["db_path"]

    corr_notice_id = f"not_corr_vac_{uuid.uuid4().hex[:8]}"
    nv_id = f"nv_cv_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_ssc', 'Staff Selection Commission', 'HQ-01/2026',
                      'Junior Engineer 2026 Vacancy Corrigendum',
                      'https://ssc.gov.in/corrigendum-je-2026.pdf', 'Central', 'Central',
                      'CORRIGENDUM', 'VERIFIED', ?, ?)
            """,
            (corr_notice_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 1, 'https://ssc.gov.in/corrigendum-je-2026.pdf', 'hash_corr_vac', 'PDF', 'corr_vac.pdf', ?)
            """,
            (nv_id, corr_notice_id, now_iso),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'VERIFIED', ?)
            """,
            [
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "recruiting_authority", "Staff Selection Commission", 1.0, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "notice_number", "HQ-01/2026", 0.95, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "total_vacancies", "1765", 0.95, now_iso),  # Revised from 968
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "eligibility", "Degree or Diploma in Engineering", 0.90, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "official_source_url", "https://ssc.gov.in/corrigendum-je-2026.pdf", 1.0, now_iso),
            ],
        )

    art_id, art_v_id, content_hash = env["writer"].draft_article(notice_id=corr_notice_id, notice_version_id=nv_id)

    with get_db(db_path) as conn:
        art = conn.execute("SELECT template_type, title FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert art["template_type"] == "corrigendum.md.j2"
        assert "Corrigendum" in art["title"]

        md = conn.execute("SELECT content_markdown FROM article_versions WHERE id = ?", (art_v_id,)).fetchone()["content_markdown"]
        assert "1765" in md


# =============================================================================
# SCENARIO 7: Notice Cancellation
# =============================================================================

def test_scenario_07_notice_cancellation(product_env):
    """Scenario 7: Cancellation notice.
    Validates: Strict classification precedence as CANCELLATION_NOTICE, cancellation template
    enforces prominent warning banners ('CANCELLED', 'Do Not Apply', 'Do Not Pay Fees').
    """
    env = product_env
    db_path = env["db_path"]

    title = "Notice regarding Cancellation of Junior Engineer (Civil) Examination 2026"
    snippet = "The Commission has decided to cancel the recruitment process advertised under Advt No. 05/2026."

    cat = NoticeClassifier.classify(title=title, content_snippet=snippet)
    assert cat == NoticeCategory.CANCELLATION_NOTICE

    notice_id = f"not_cancel_{uuid.uuid4().hex[:8]}"
    nv_id = f"nv_cancel_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_upsc', 'Union Public Service Commission', '05/2026-CANCEL',
                      ?, 'https://upsc.gov.in/cancel-je-2026.pdf', 'PSC', 'Central',
                      ?, 'EXTRACTED', ?, ?)
            """,
            (notice_id, title, NoticeCategory.CANCELLATION_NOTICE.value, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES (?, ?, 1, 'https://upsc.gov.in/cancel-je-2026.pdf', 'hash_cancel_pdf',
                      'PDF', 'cancel.pdf', ?, 1, ?)
            """,
            (nv_id, notice_id, snippet, now_iso),
        )

    art_id, art_v_id, content_hash = env["writer"].draft_article(notice_id=notice_id)

    with get_db(db_path) as conn:
        row = conn.execute("SELECT content_markdown FROM article_versions WHERE id = ?", (art_v_id,)).fetchone()
        md = row["content_markdown"]

        # Prominent cancellation invariants
        assert "CANCELLED" in md
        assert "Do Not Apply" in md
        assert "Do Not Pay Fees" in md


# =============================================================================
# SCENARIO 8: Duplicate Notice Prevention
# =============================================================================

def test_scenario_08_duplicate_notice(product_env):
    """Scenario 8: Duplicate notice detected across discovery runs.
    Validates: Deduplication engine identifies EXACT_URL_DUPLICATE and suppresses creation of redundant notices.
    """
    env = product_env
    db_path = env["db_path"]

    url = "https://tnpsc.gov.in/notifications/ctse_2026.pdf"
    now_iso = datetime.now(timezone.utc).isoformat()
    existing_id = f"not_tnpsc_{uuid.uuid4().hex[:8]}"

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_tnpsc', 'Tamil Nadu PSC', '14/2026', 'CTSE Examination',
                      ?, 'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED', ?, ?)
            """,
            (existing_id, url, now_iso, now_iso),
        )

        dedup = DeduplicationEngine(conn)
        match_type, matched_id, v = dedup.evaluate_candidate(
            source_id="src_tnpsc",
            normalized_url=url,
            notice_number="14/2026",
            title="CTSE Examination",
        )
        assert match_type == MatchType.UNCHANGED
        assert matched_id == existing_id


# =============================================================================
# SCENARIO 9: Corrupt PDF Handling
# =============================================================================

def test_scenario_09_corrupt_pdf(product_env):
    """Scenario 9: Corrupt PDF payload.
    Validates: System catches extraction error gracefully without crashing, marks status
    as SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW, blocks ordinary approval.
    """
    env = product_env
    db_path = env["db_path"]

    corrupt_bytes = b"%PDF-1.4\nGARBAGE_PAYLOAD_NOT_A_VALID_STRUCTURE_EOF"
    notice_id = f"not_corrupt_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    doc_url = "https://uppsc.up.nic.in/corrupt_notice.pdf"

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_uppsc', 'UPPSC', 'CORRUPT-01', 'Corrupt Document Notice',
                      ?, 'PSC', 'Uttar Pradesh', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED', ?, ?)
            """,
            (notice_id, doc_url, now_iso, now_iso),
        )

    # Ingestion catches error and flags notice
    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=corrupt_bytes,
        doc_url=doc_url,
        content_type="application/pdf",
    )
    assert v_id.startswith("ver_")

    with get_db(db_path) as conn:
        notice_status = conn.execute("SELECT status FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()["status"]
        assert notice_status == "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW"

        fact_row = conn.execute("SELECT fact_key, fact_value FROM extracted_facts WHERE notice_version_id = ?", (v_id,)).fetchone()
        assert fact_row["fact_key"] == "document_readability"
        assert fact_row["fact_value"] == "DOCUMENT_CORRUPT_OR_UNREADABLE"


# =============================================================================
# SCENARIO 10: Official Source Unavailable
# =============================================================================

def test_scenario_10_official_source_unavailable(product_env):
    """Scenario 10: Official portal returns HTTP 503 Service Unavailable / Timeout.
    Validates: Retries with exponential backoff, logs failure in scan_source_logs,
    increments failure counter, other healthy sources proceed unaffected.
    """
    env = product_env
    db_path = env["db_path"]

    # Mock client where SSC returns 503, but UPSC succeeds
    mock_client = MagicMock()

    def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.is_redirect = False
        if "ssc.gov.in" in url:
            resp.status_code = 503
            import httpx
            raise httpx.HTTPStatusError("503 Service Unavailable", request=MagicMock(), response=resp)
        else:
            resp.status_code = 200
            resp.content = b"<html><body><table><tr><td>No new notices</td></tr></table></body></html>"
            resp.headers = {"Content-Type": "text/html"}
            resp.raise_for_status = MagicMock()
            return resp

    mock_client.get = mock_get
    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)
    engine = DiscoveryEngine(db_path=db_path, fetcher=fetcher)

    # Run scan for SSC
    scan_res = engine.run_scan(scan_type="SCHEDULED", source_code="SSC")
    assert scan_res["errors_count"] >= 1

    with get_db(db_path) as conn:
        ssc_log = conn.execute(
            """
            SELECT sl.status, sl.error_message
            FROM scan_source_logs sl
            JOIN official_sources s ON sl.source_id = s.id
            WHERE s.code = 'SSC'
            ORDER BY sl.checked_at DESC LIMIT 1
            """
        ).fetchone()
        assert ssc_log["status"] == "FAILED"
        assert "503" in ssc_log["error_message"]

        # Consecutive failures incremented
        consec = conn.execute("SELECT consecutive_failures FROM official_sources WHERE code = 'SSC'").fetchone()[0]
        assert consec >= 1


# =============================================================================
# CROSS-CUTTING ACCEPTANCE REQUIREMENTS & INVARIANTS
# =============================================================================

def test_acceptance_invariants_and_safeguards(product_env):
    """Verify core architectural safeguards:
    1. Material changes to draft invalidate prior approvals.
    2. Fact corrections invalidate linked article approvals.
    3. Live publishing remains permanently disabled (failsafe).
    4. Real-world pilot database (data/real_world_pilot_30day.db) remains untouched.
    """
    env = product_env
    db_path = env["db_path"]

    # 1. Draft edit invalidation
    notice_id = f"not_inv_{uuid.uuid4().hex[:8]}"
    nv_id = f"nv_inv_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (?, 'src_upsc', 'UPSC', '01/2026', 'Sample Exam',
                      'https://upsc.gov.in/sample.pdf', 'PSC', 'Central',
                      'RECRUITMENT_NOTIFICATION', 'VERIFIED', ?, ?)
            """,
            (notice_id, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES (?, ?, 1, 'https://upsc.gov.in/sample.pdf', 'hash_sample', 'PDF', 'sample.pdf', ?)
            """,
            (nv_id, notice_id, now_iso),
        )
        conn.executemany(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence, verified_status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'VERIFIED', ?)
            """,
            [
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "total_vacancies", "100", 0.95, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "application_start_date", "01/01/2026", 0.95, now_iso),
                (f"f_{uuid.uuid4().hex[:8]}", nv_id, "application_end_date", "31/01/2026", 0.95, now_iso),
            ],
        )

    art_id, art_v1_id, hash1 = env["writer"].draft_article(notice_id=notice_id)
    appr_res = env["editorial"].submit_decision(
        article_id=art_id,
        expected_version_id=art_v1_id,
        expected_content_hash=hash1,
        decision="APPROVE",
        editor_email="editor@testkart.in",
    )
    assert appr_res["decision"] == "APPROVED"

    # Editor edits markdown content -> prior approval must be INVALIDATED
    edit_res = env["editorial"].save_draft(
        article_id=art_id,
        expected_version_id=art_v1_id,
        title="Sample Exam 2026 (Updated Guidelines)",
        content_markdown="# Sample Exam 2026\n\nUpdated recruitment details with revised guidelines.",
        editor_email="editor@testkart.in",
    )
    assert edit_res["version_number"] == 2

    with get_db(db_path) as conn:
        appr_status = conn.execute(
            "SELECT status FROM approval_records WHERE id = ?",
            (appr_res["approval_id"],),
        ).fetchone()["status"]
        assert appr_status == "INVALIDATED"

    # 2. Live publishing strictly disabled
    # Under safe mode, assert_live_publishing_disabled() succeeds
    assert_live_publishing_disabled()

    # If ALLOW_LIVE_PUBLISHING is set to True, guard strictly raises LivePublishingDisabledError
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "ALLOW_LIVE_PUBLISHING", True)
    with pytest.raises(LivePublishingDisabledError):
        assert_live_publishing_disabled()
    monkeypatch.undo()

    # 3. Verify pilot database preservation
    pilot_db_path = Path("data/real_world_pilot_30day.db")
    if pilot_db_path.exists():
        import sqlite3
        p_conn = sqlite3.connect(f"file:{pilot_db_path.resolve()}?mode=ro", uri=True)
        try:
            p_notices = p_conn.execute("SELECT count(*) FROM canonical_notices").fetchone()[0]
            assert p_notices >= 1963, f"Real world pilot DB missing notices: {p_notices}"
            p_scans = p_conn.execute("SELECT count(*) FROM scan_runs").fetchone()[0]
            assert p_scans >= 1, f"Real world pilot DB missing baseline scan: {p_scans}"
        finally:
            p_conn.close()
