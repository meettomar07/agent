"""End-to-End Editorial Workflow Acceptance Tests.

Validates the complete local editorial review workflow using real official notices:
- Discovery & deduplication
- Document retrieval & fact verification
- Draft generation & QA checks
- Reviewer evidence audit & confirmation/correction
- Approval eligibility & audited overrides
- Simulated mock publication
"""

import hashlib
import json
import re
from pathlib import Path
import pymupdf
import pytest

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.config import settings
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.discovery.deduplication import DeduplicationEngine, MatchType
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
from testkart_intelligence.publishing.guard import LivePublishingDisabledError, assert_live_publishing_disabled


@pytest.fixture
def acceptance_env(tmp_path: Path, monkeypatch):
    """Isolated environment for acceptance testing."""
    test_db = tmp_path / "acceptance.db"
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
        "service": EditorialService(db_path=test_db),
        "verifier": VerificationAgent(db_path=test_db),
        "writer": WritingAgent(db_path=test_db),
        "qa_agent": QualityAssuranceAgent(db_path=test_db),
        "publisher": MockPublisher(db_path=test_db),
    }


def test_scenario_1_all_major_fields_present_e2e(acceptance_env):
    """Scenario 1: All major fields present in real TNPSC CTSE notice.
    Full lifecycle: Discovery -> Ingestion -> Draft -> QA -> Evidence Audit -> Approval -> Mock Publish.
    """
    env = acceptance_env
    pdf_path = Path("data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf")
    pdf_bytes = pdf_path.read_bytes()

    # 1. Discovery & Deduplication
    with get_db(env["db_path"]) as conn:
        dedup = DeduplicationEngine(conn)
        match_type, _, _ = dedup.evaluate_candidate(
            source_id="src_tnpsc",
            normalized_url="https://tnpsc.gov.in/notifications/dev_08.pdf",
            notice_number="11/2024",
        )
        assert match_type == MatchType.NEW

        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_s1', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '11/2024',
                'Combined Technical Services Examination (Diploma / Non-Standard Posts) 2024',
                'https://tnpsc.gov.in/notifications/dev_08.pdf',
                'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    # 2. Ingestion & Extraction
    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id="not_s1",
        doc_bytes=pdf_bytes,
        doc_url="https://tnpsc.gov.in/notifications/dev_08.pdf",
        content_type="application/pdf",
    )
    assert len(facts) >= 6

    # 3. Draft generation
    art_id, arv_id, content_hash = env["writer"].draft_article("not_s1")
    assert art_id and arv_id and content_hash

    # 4. QA
    qa_pass, qa_score, _ = env["qa_agent"].inspect_and_evaluate(arv_id)
    assert qa_pass is True
    assert qa_score >= 85.0

    # 5. Reviewer Evidence Audit
    editor_data = env["service"].get_draft_editor(art_id)
    assert editor_data["can_normally_approve"] is True
    assert len(editor_data["unresolved_issues"]) == 0

    # 6. Explicit Approval
    app_res = env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=arv_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        notes="All fields verified against official TNPSC notification 11/2024",
    )
    assert app_res["decision"] == "APPROVED"
    assert app_res["live_publishing_enabled"] is False

    # 7. Mock Publication & Idempotency
    pub_res = env["publisher"].publish(
        article_version_id=arv_id,
        content_hash=content_hash,
        approval_record_id=app_res["approval_id"],
    )
    assert pub_res["status"] == "COMPLETED"
    assert pub_res["is_mock"] is True
    assert pub_res["published_url"].startswith("https://mock.testkart.local/blog/")

    # Repeat call returns identical job
    pub_repeat = env["publisher"].publish(
        article_version_id=arv_id,
        content_hash=content_hash,
        approval_record_id=app_res["approval_id"],
    )
    assert pub_repeat["idempotent"] is True
    assert pub_repeat["job_id"] == pub_res["job_id"]


def test_scenario_2_missing_critical_fields_blocks_ordinary_approval(acceptance_env):
    """Scenario 2: Recruitment notice with missing application dates.
    Must block ordinary approval; requires recorded editorial override with justification.
    """
    env = acceptance_env
    html_path = Path("data/development_notices/dev_10_upsc_homoeopathic_physician_notice.html")
    html_bytes = html_path.read_bytes()

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_s2', 'src_upsc', 'Union Public Service Commission', '',
                '04 Posts of Homoeopathic Physician in Directorate of AYUSH',
                'https://upsc.gov.in/recruitment/dev_10.html',
                'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id="not_s2",
        doc_bytes=html_bytes,
        doc_url="https://upsc.gov.in/recruitment/dev_10.html",
        content_type="text/html",
    )

    art_id, arv_id, content_hash = env["writer"].draft_article("not_s2")
    qa_pass, qa_score, _ = env["qa_agent"].inspect_and_evaluate(arv_id)
    assert qa_pass is False  # Missing dates fails QA

    editor = env["service"].get_draft_editor(art_id)
    assert editor["can_normally_approve"] is False
    assert any("Application Start Date" in iss for iss in editor["unresolved_issues"])

    # Ordinary approval must be BLOCKED
    with pytest.raises(ApprovalBlockedError):
        env["service"].submit_decision(
            article_id=art_id,
            expected_version_id=arv_id,
            expected_content_hash=content_hash,
            decision="APPROVE",
            is_override=False,
        )

    # Override with insufficient reason (< 10 chars) rejected
    with pytest.raises(EditorialSecurityError):
        env["service"].submit_decision(
            article_id=art_id,
            expected_version_id=arv_id,
            expected_content_hash=content_hash,
            decision="APPROVE",
            is_override=True,
            override_reason="short",
        )

    # Valid override succeeds and logs audit record
    app_override = env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=arv_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        is_override=True,
        override_reason="Shortlist notice; application dates closed in initial advertisement verified.",
    )
    assert app_override["decision"] == "APPROVED"
    assert app_override["is_override"] is True

    with get_db(env["db_path"]) as conn:
        aud = conn.execute(
            "SELECT action, payload_json FROM audit_events WHERE entity_id = ?",
            (app_override["approval_id"],),
        ).fetchone()
        assert aud["action"] == "EDITORIAL_OVERRIDE_APPROVED"


def test_scenario_3_conflicting_ambiguous_values_blocks_and_corrects(acceptance_env):
    """Scenario 3: Contradictory application dates block ordinary approval.
    Reviewer corrects fact -> approval unblocks after draft update.
    """
    env = acceptance_env

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_s3', 'src_ssc', 'Staff Selection Commission', '15/2026',
                'Junior Engineer Examination 2026 Notification',
                'https://ssc.gov.in/notice_s3.pdf',
                'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES (
                'nver_s3', 'not_s3', 1, 'https://ssc.gov.in/notice_s3.pdf', 'hash_s3',
                'PDF', 's3.pdf', 'SSC JE 2026 text with conflicting dates', 4, '2026-10-29T10:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence,
                evidence_text, page_number, verified_status, created_at
            ) VALUES
            ('fact_s3_vac', 'nver_s3', 'total_vacancies', '1200', 0.95, 'Vacancies: 1200', 1, 'VERIFIED', '2026-10-29T10:00:00Z'),
            ('fact_s3_start', 'nver_s3', 'application_start_date', '01/10/2026', 0.95, 'Start: 01/10/2026', 1, 'VERIFIED', '2026-10-29T10:00:00Z'),
            ('fact_s3_end', 'nver_s3', 'application_end_date', '31/10/2026', 0.60, 'Conflicting: 31/10/2026 vs 05/11/2026', 1, 'CONTRADICTORY', '2026-10-29T10:00:00Z'),
            ('fact_s3_exam', 'nver_s3', 'exam_date', '15/12/2026', 0.90, 'Exam: 15/12/2026', 2, 'VERIFIED', '2026-10-29T10:00:00Z'),
            ('fact_s3_age', 'nver_s3', 'age_limit', '18 to 30 years', 0.90, 'Age: 18 to 30 years', 2, 'VERIFIED', '2026-10-29T10:00:00Z'),
            ('fact_s3_qual', 'nver_s3', 'eligibility', 'Degree or Diploma in Engineering', 0.90, 'Degree requirement', 3, 'VERIFIED', '2026-10-29T10:00:00Z')
            """
        )

    art_id, arv_id, content_hash = env["writer"].draft_article("not_s3")
    editor = env["service"].get_draft_editor(art_id)
    assert editor["can_normally_approve"] is False

    with pytest.raises(ApprovalBlockedError):
        env["service"].submit_decision(
            article_id=art_id,
            expected_version_id=arv_id,
            expected_content_hash=content_hash,
            decision="APPROVE",
            is_override=False,
        )

    # Reviewer corrects the contradictory date
    corr_res = env["service"].correct_fact(
        fact_id="fact_s3_end",
        corrected_value="05/11/2026",
        reason="Corrigendum para 3 extended fee and online submission cutoff to 05/11/2026",
    )
    assert corr_res["corrected_value"] == "05/11/2026"
    assert corr_res["is_confirmed"] is True

    # Linked article status is in safe reviewable state
    with get_db(env["db_path"]) as conn:
        art_st = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,)).fetchone()["status"]
        assert art_st in ("DRAFT", "QA_FAILED")

    # Update draft markdown to reflect corrected date
    cur_v = editor["current_version"]
    updated_md = cur_v["content_markdown"].replace("Requires Editor Review", "05/11/2026")
    save_res = env["service"].save_draft(
        article_id=art_id,
        expected_version_id=cur_v["id"],
        title=cur_v["title"],
        content_markdown=updated_md,
    )
    assert save_res["qa_passed"] is True

    # Now ordinary approval succeeds
    editor_updated = env["service"].get_draft_editor(art_id)
    assert editor_updated["can_normally_approve"] is True

    app_res = env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=save_res["version_id"],
        expected_content_hash=save_res["content_hash"],
        decision="APPROVE",
        notes="Approved after confirming closing date extension",
    )
    assert app_res["decision"] == "APPROVED"


def test_scenario_4_multi_cadre_breakdown(acceptance_env):
    """Scenario 4: Multi-cadre vacancy table with grand total (TNPSC Non-Interview Posts)."""
    env = acceptance_env
    pdf_path = Path("data/development_notices/dev_09_tnpsc_cts_non_interview_posts.pdf")

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_s4', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '9/2024',
                'Combined Technical Services Examination (Non-Interview Posts)',
                'https://tnpsc.gov.in/notifications/dev_09.pdf',
                'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id="not_s4",
        doc_bytes=pdf_path.read_bytes(),
        doc_url="https://tnpsc.gov.in/notifications/dev_09.pdf",
        content_type="application/pdf",
    )
    vac_fact = [f for f in facts if f.key == "total_vacancies"][0]
    assert vac_fact.value == "654"

    art_id, arv_id, content_hash = env["writer"].draft_article("not_s4")
    editor = env["service"].get_draft_editor(art_id)
    assert editor["can_normally_approve"] is True

    app_res = env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=arv_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        notes="Cadre breakdown verified: 654 vacancies across 8 cadres",
    )
    assert app_res["decision"] == "APPROVED"


def test_scenario_5_multi_stage_exam_schedule(acceptance_env):
    """Scenario 5: Multi-stage examination schedule (Paper-I & Paper-II).
    Post-wise vacancies lack grand total row -> blocks approval; unblocked via audited override.
    """
    env = acceptance_env
    pdf_path = Path("data/generalization_notices/gen_01_tnpsc_assistant_jailor__men___women.pdf")

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_s5', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '07/2023',
                'Assistant Jailor (Men) and Assistant Jailor (Women) in Prisons Department',
                'https://tnpsc.gov.in/notifications/gen_01.pdf',
                'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id="not_s5",
        doc_bytes=pdf_path.read_bytes(),
        doc_url="https://tnpsc.gov.in/notifications/gen_01.pdf",
        content_type="application/pdf",
    )
    exam_fact = [f for f in facts if f.key == "exam_date"][0]
    assert "01.07.2023" in exam_fact.value
    assert "Schedule Table" in exam_fact.evidence_text

    art_id, arv_id, content_hash = env["writer"].draft_article("not_s5")
    editor = env["service"].get_draft_editor(art_id)

    # Post-wise vacancies (Men: 56, Women: 3) lacks explicit grand total row -> ordinary approval blocked
    assert editor["can_normally_approve"] is False
    assert any("Total Vacancies" in iss for iss in editor["unresolved_issues"])

    with pytest.raises(ApprovalBlockedError):
        env["service"].submit_decision(
            article_id=art_id,
            expected_version_id=arv_id,
            expected_content_hash=content_hash,
            decision="APPROVE",
            is_override=False,
        )

    # Reviewer approves via audited override with recorded justification
    app_override = env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=arv_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        is_override=True,
        override_reason="Multi-stage schedule Paper I & II verified; summed post-wise cadre rows (Men 56 + Women 3 = 59) against official annexure.",
    )
    assert app_override["decision"] == "APPROVED"
    assert app_override["is_override"] is True


def test_scenario_6_age_relaxations_modal_selection(acceptance_env):
    """Scenario 6: Age table with reserved concession rows ("No maximum age limit")
    alongside General category limit (32 years). Must not invert to minimum age (18).
    """
    env = acceptance_env
    pdf_path = Path("data/generalization_notices/gen_02_tnpsc_tourist_officer.pdf")

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_s6', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '02/2023',
                'Tourist Officer in Tamil Nadu General Service',
                'https://tnpsc.gov.in/notifications/gen_02.pdf',
                'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id="not_s6",
        doc_bytes=pdf_path.read_bytes(),
        doc_url="https://tnpsc.gov.in/notifications/gen_02.pdf",
        content_type="application/pdf",
    )
    age_fact = [f for f in facts if f.key == "age_limit"][0]
    assert "32" in age_fact.value
    assert age_fact.status == "VERIFIED"

    art_id, arv_id, content_hash = env["writer"].draft_article("not_s6")
    editor = env["service"].get_draft_editor(art_id)
    assert editor["can_normally_approve"] is True

    app_res = env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=arv_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        notes="General category age limit 32 years verified",
    )
    assert app_res["decision"] == "APPROVED"


def test_scenario_7_qualification_conditions_in_tables(acceptance_env):
    """Scenario 7: Qualification requirements embedded in multi-row table."""
    env = acceptance_env
    pdf_path = Path("data/new_validation_notices/new_val_12_tnpsc_combined_engineering_services.pdf")

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_s7', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '23/2023',
                'Combined Engineering Services Examination 2023',
                'https://tnpsc.gov.in/notifications/nv12.pdf',
                'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id="not_s7",
        doc_bytes=pdf_path.read_bytes(),
        doc_url="https://tnpsc.gov.in/notifications/nv12.pdf",
        content_type="application/pdf",
    )
    qual_fact = [f for f in facts if f.key == "eligibility"][0]
    assert "Engineering" in qual_fact.value
    assert qual_fact.status == "VERIFIED"

    art_id, arv_id, content_hash = env["writer"].draft_article("not_s7")
    editor = env["service"].get_draft_editor(art_id)
    assert editor["can_normally_approve"] is True

    app_res = env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=arv_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        notes="Engineering qualification verified from official table",
    )
    assert app_res["decision"] == "APPROVED"


def test_scenario_8_no_explicit_total_vacancies_blocks_and_corrects(acceptance_env):
    """Scenario 8: No explicit total vacancies count (tabular breakdown only).
    Flagged as POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW; blocks approval until confirmed.
    """
    env = acceptance_env

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_s8', 'src_uppsc', 'Uttar Pradesh Public Service Commission', 'A-1/E-1/2026',
                'UPPSC Combined State Engineering Services Exam',
                'https://uppsc.up.nic.in/notice_s8.pdf',
                'PSC', 'Uttar Pradesh', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES (
                'nver_s8', 'not_s8', 1, 'https://uppsc.up.nic.in/notice_s8.pdf', 'hash_s8',
                'PDF', 's8.pdf', 'UPPSC engineering services text', 5, '2026-10-29T10:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence,
                evidence_text, page_number, verified_status, created_at
            ) VALUES
            ('fact_s8_vac', 'nver_s8', 'total_vacancies', 'POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW', 0.50, 'Post-wise table: Civil 150, Mechanical 60, Electrical 25', 2, 'UNVERIFIED', '2026-10-29T10:00:00Z'),
            ('fact_s8_start', 'nver_s8', 'application_start_date', '01/11/2026', 0.95, 'Start 01/11/2026', 1, 'VERIFIED', '2026-10-29T10:00:00Z'),
            ('fact_s8_end', 'nver_s8', 'application_end_date', '30/11/2026', 0.95, 'End 30/11/2026', 1, 'VERIFIED', '2026-10-29T10:00:00Z'),
            ('fact_s8_exam', 'nver_s8', 'exam_date', '28/02/2027', 0.90, 'Exam 28/02/2027', 2, 'VERIFIED', '2026-10-29T10:00:00Z'),
            ('fact_s8_age', 'nver_s8', 'age_limit', '21 to 40 years', 0.90, 'Age 21 to 40', 2, 'VERIFIED', '2026-10-29T10:00:00Z'),
            ('fact_s8_qual', 'nver_s8', 'eligibility', 'B.Tech in Civil / Mechanical / Electrical', 0.90, 'Engineering Degree', 3, 'VERIFIED', '2026-10-29T10:00:00Z')
            """
        )

    art_id, arv_id, content_hash = env["writer"].draft_article("not_s8")
    editor = env["service"].get_draft_editor(art_id)
    assert editor["can_normally_approve"] is False

    with pytest.raises(ApprovalBlockedError):
        env["service"].submit_decision(
            article_id=art_id,
            expected_version_id=arv_id,
            expected_content_hash=content_hash,
            decision="APPROVE",
            is_override=False,
        )

    # Reviewer sums post rows: 150 + 60 + 25 = 235
    corr_res = env["service"].correct_fact(
        fact_id="fact_s8_vac",
        corrected_value="235",
        reason="Summed cadre rows: Civil 150 + Mechanical 60 + Electrical 25 = 235 confirmed",
    )
    assert corr_res["corrected_value"] == "235"

    cur_v = editor["current_version"]
    updated_md = cur_v["content_markdown"].replace("POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW", "235")
    save_res = env["service"].save_draft(
        article_id=art_id,
        expected_version_id=cur_v["id"],
        title=cur_v["title"],
        content_markdown=updated_md,
    )

    editor_updated = env["service"].get_draft_editor(art_id)
    assert editor_updated["can_normally_approve"] is True

    app_res = env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=save_res["version_id"],
        expected_content_hash=save_res["content_hash"],
        decision="APPROVE",
        notes="Total 235 confirmed by summing cadre rows",
    )
    assert app_res["decision"] == "APPROVED"


def test_governance_safeguard_material_edit_invalidates_approval(acceptance_env):
    """Safeguard: Any edit to an approved article invalidates approval and resets status."""
    env = acceptance_env
    pdf_path = Path("data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf")

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_sg1', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '11/2024',
                'Combined Technical Services Examination 2024',
                'https://tnpsc.gov.in/notifications/dev_08.pdf',
                'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    env["verifier"].process_and_verify_document(
        notice_id="not_sg1",
        doc_bytes=pdf_path.read_bytes(),
        doc_url="https://tnpsc.gov.in/notifications/dev_08.pdf",
        content_type="application/pdf",
    )
    art_id, arv_id, content_hash = env["writer"].draft_article("not_sg1")
    app_res = env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=arv_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
    )
    assert app_res["decision"] == "APPROVED"

    # Editor modifies draft
    save_res = env["service"].save_draft(
        article_id=art_id,
        expected_version_id=arv_id,
        title="Updated Title",
        content_markdown="# Modified Article Content\n\nNew verified paragraph.",
    )
    assert save_res["version_number"] == 2

    # Verify prior approval was invalidated
    with get_db(env["db_path"]) as conn:
        app_rec = conn.execute(
            "SELECT status FROM approval_records WHERE article_version_id = ?",
            (arv_id,),
        ).fetchone()
        assert app_rec["status"] == "INVALIDATED"


def test_governance_safeguard_fact_correction_invalidates_approval(acceptance_env):
    """Safeguard: Correcting an extracted fact on an approved notice invalidates article approval."""
    env = acceptance_env
    pdf_path = Path("data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf")

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_sg2', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '11/2024',
                'Combined Technical Services Examination 2024',
                'https://tnpsc.gov.in/notifications/dev_08.pdf',
                'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    v_id, facts = env["verifier"].process_and_verify_document(
        notice_id="not_sg2",
        doc_bytes=pdf_path.read_bytes(),
        doc_url="https://tnpsc.gov.in/notifications/dev_08.pdf",
        content_type="application/pdf",
    )
    art_id, arv_id, content_hash = env["writer"].draft_article("not_sg2")
    env["service"].submit_decision(
        article_id=art_id,
        expected_version_id=arv_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
    )

    with get_db(env["db_path"]) as conn:
        f_row = conn.execute(
            "SELECT id FROM extracted_facts WHERE notice_version_id = ? AND fact_key = 'total_vacancies'",
            (v_id,),
        ).fetchone()

    # Reviewer corrects fact post-approval
    env["service"].correct_fact(
        fact_id=f_row["id"],
        corrected_value="865",
        reason="Corrigendum added 4 additional posts to vacancy table",
    )

    # Approval must be INVALIDATED and article reset to DRAFT
    with get_db(env["db_path"]) as conn:
        app_rec = conn.execute(
            "SELECT status FROM approval_records WHERE article_version_id = ?",
            (arv_id,),
        ).fetchone()
        assert app_rec["status"] == "INVALIDATED"
        art_rec = conn.execute("SELECT status FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert art_rec["status"] == "DRAFT"


def test_governance_safeguard_stale_version_and_content_hash_protection(acceptance_env):
    """Safeguard: Stale version ID and content hash mismatch strictly rejected."""
    env = acceptance_env
    pdf_path = Path("data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf")

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_sg3', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '11/2024',
                'Combined Technical Services Examination 2024',
                'https://tnpsc.gov.in/notifications/dev_08.pdf',
                'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    env["verifier"].process_and_verify_document(
        notice_id="not_sg3",
        doc_bytes=pdf_path.read_bytes(),
        doc_url="https://tnpsc.gov.in/notifications/dev_08.pdf",
        content_type="application/pdf",
    )
    art_id, arv_id, content_hash = env["writer"].draft_article("not_sg3")

    # Stale version ID
    with pytest.raises(StaleVersionConflictError):
        env["service"].submit_decision(
            article_id=art_id,
            expected_version_id="stale_version_id",
            expected_content_hash=content_hash,
            decision="APPROVE",
        )

    # Mismatched content hash
    with pytest.raises(StaleVersionConflictError):
        env["service"].submit_decision(
            article_id=art_id,
            expected_version_id=arv_id,
            expected_content_hash="bad_hash_value",
            decision="APPROVE",
        )


def test_governance_safeguard_deduplication_prevents_duplicate_articles(acceptance_env):
    """Safeguard: Duplicate notice scans do not silently produce duplicate articles."""
    env = acceptance_env

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_sg4', 'src_tnpsc', 'Tamil Nadu Public Service Commission', '11/2024',
                'Combined Technical Services Examination 2024',
                'https://tnpsc.gov.in/notifications/dev_08.pdf',
                'PSC', 'Tamil Nadu', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES (
                'nver_sg4', 'not_sg4', 1, 'https://tnpsc.gov.in/notifications/dev_08.pdf', 'hash_dev08',
                'PDF', 'dev08.pdf', 'CTSE notice text', 5, '2026-10-29T10:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (id, notice_version_id, fact_key, fact_value, confidence, evidence_text, page_number, verified_status, created_at)
            VALUES ('f_sg4', 'nver_sg4', 'total_vacancies', '861', 0.95, '861 posts', 1, 'VERIFIED', '2026-10-29T10:00:00Z')
            """
        )

        dedup = DeduplicationEngine(conn)
        mtype, exist_id, _ = dedup.evaluate_candidate(
            source_id="src_tnpsc",
            normalized_url="https://tnpsc.gov.in/notifications/dev_08.pdf",
            notice_number="11/2024",
        )
        assert mtype == MatchType.UNCHANGED
        assert exist_id == "not_sg4"

    art1_id, _, _ = env["writer"].draft_article("not_sg4")
    art2_id, _, _ = env["writer"].draft_article("not_sg4")
    assert art1_id == art2_id

    with get_db(env["db_path"]) as conn:
        c = conn.execute("SELECT count(*) as c FROM blog_articles WHERE canonical_notice_id = 'not_sg4'").fetchone()["c"]
        assert c == 1


def test_governance_safeguard_unreadable_scanned_notice_blocks_drafting(acceptance_env):
    """Safeguard: Scanned or unreadable notices halt automated drafting."""
    env = acceptance_env

    # Generate an unreadable image/blank page with no extractable text
    doc = pymupdf.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    with get_db(env["db_path"]) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_scanned', 'src_nta', 'National Testing Agency', 'NTA/01',
                'NTA Exam Calendar Scanned',
                'https://nta.ac.in/scanned.pdf',
                'Teaching/Education', 'Central', 'EXAM_DATE_ANNOUNCEMENT', 'DISCOVERED',
                '2026-10-29T10:00:00Z', '2026-10-29T10:00:00Z'
            )
            """
        )

    env["verifier"].process_and_verify_document(
        notice_id="not_scanned",
        doc_bytes=pdf_bytes,
        doc_url="https://nta.ac.in/scanned.pdf",
        content_type="application/pdf",
    )

    with get_db(env["db_path"]) as conn:
        st = conn.execute("SELECT status FROM canonical_notices WHERE id = 'not_scanned'").fetchone()["status"]
        assert st == "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW"

    with pytest.raises(ValueError, match="flagged for human review"):
        env["writer"].draft_article("not_scanned")


def test_governance_safeguard_live_publishing_strictly_disabled_failsafe():
    """Safeguard: Live publishing disabled check strictly raises LivePublishingDisabledError."""
    assert_live_publishing_disabled()
    try:
        settings.ALLOW_LIVE_PUBLISHING = True
        with pytest.raises(LivePublishingDisabledError):
            assert_live_publishing_disabled()
    finally:
        settings.ALLOW_LIVE_PUBLISHING = False
