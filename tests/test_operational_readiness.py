"""Tests for Testkart Operational Readiness:
1. Notice-type classification across all official categories
2. Parent notice linking (unambiguous matching vs ambiguous human review flagging)
3. Template routing and QA consistency
4. Scheduler lifecycle, duplicate prevention, and clean startup/shutdown
5. Editorial override governance and unverified field auditing
"""

import json
from pathlib import Path
import pytest

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.config import settings
from testkart_intelligence.registry.service import seed_sources_if_empty
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.editorial.service import (
    EditorialService,
    ApprovalBlockedError,
    EditorialSecurityError,
)
from testkart_intelligence.scheduler.job_runner import (
    ScanScheduler,
    SchedulerAlreadyRunningError,
)


@pytest.fixture
def readiness_db(tmp_path: Path, monkeypatch):
    test_db = tmp_path / "readiness.db"
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    monkeypatch.setattr(settings, "DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr(settings, "ALLOW_LIVE_PUBLISHING", False)
    monkeypatch.setattr(settings, "ENABLE_EMAIL_NOTIFICATIONS", False)

    init_db(test_db)
    with get_db(test_db) as conn:
        seed_sources_if_empty(conn)

    return test_db


# =========================================================================
# 1. Notice-Type Classification Tests
# =========================================================================

def test_classification_across_all_nine_official_types():
    """Verify accurate classification across all required notice types."""
    # 1. New recruitment notification
    cat = NoticeClassifier.classify(
        title="Direct Recruitment to 500 Posts of Assistant Engineer (Civil)",
        url="https://tnpsc.gov.in/notifications/advt_10.pdf"
    )
    assert cat == NoticeCategory.RECRUITMENT_NOTIFICATION

    # 2. Recruitment addenda and corrigenda
    cat_add = NoticeClassifier.classify(
        title="Addendum Notice: 03 Posts of Law Officer, Government of NCT of Delhi",
        url="https://upsc.gov.in/whats-new/addendum_03_law_officer"
    )
    assert cat_add == NoticeCategory.RECRUITMENT_ADDENDUM

    cat_corr = NoticeClassifier.classify(
        title="Corrigendum in respect of Advt No. 04/2026 for Junior Engineer",
        url="https://ssc.gov.in/notices/corrigendum_je.pdf"
    )
    assert cat_corr == NoticeCategory.CORRIGENDUM

    # 3. Application deadline extensions
    cat_ext = NoticeClassifier.classify(
        title="Extension of Last Date for Submission of Online Application Form",
        url="https://nta.ac.in/Download/Notice/extension_ugc_net.pdf"
    )
    assert cat_ext == NoticeCategory.APPLICATION_WINDOW_UPDATE

    # 4. Exam dates and schedule updates
    cat_sched = NoticeClassifier.classify(
        title="Examination Schedule for Combined Graduate Level Tier-II Examination 2026",
        url="https://ssc.gov.in/notices/cgl_tier2_schedule.pdf"
    )
    assert cat_sched == NoticeCategory.EXAM_DATE_ANNOUNCEMENT

    # 5. Admit cards and answer keys
    cat_admit = NoticeClassifier.classify(
        title="Release of Admit Card / Hall Ticket for Joint Entrance Examination (Main)",
        url="https://nta.ac.in/Download/admit_card_jee.pdf"
    )
    assert cat_admit == NoticeCategory.ADMIT_CARD_RELEASE

    cat_key = NoticeClassifier.classify(
        title="Uploading of Tentative Answer Keys along with Candidates' Response Sheets",
        url="https://ssc.gov.in/notices/chsl_tentative_keys.pdf"
    )
    assert cat_key == NoticeCategory.ANSWER_KEY

    # 6. Results
    cat_res = NoticeClassifier.classify(
        title="Declaration of Final Result and Cutoff Marks for Combined Civil Services Exam",
        url="https://tnpsc.gov.in/results/ccse_final_result.pdf"
    )
    assert cat_res == NoticeCategory.EXAM_RESULT

    # 7. Admissions and entrance examinations
    cat_adm = NoticeClassifier.classify(
        title="Admission into Rashtriya Indian Military College (RIMC), Dehradun for Jan 2025 Term",
        url="https://tnpsc.gov.in/notices/rimc_admission_2025.pdf"
    )
    assert cat_adm == NoticeCategory.ADMISSION_OR_ENTRANCE_EXAM

    cat_jee = NoticeClassifier.classify(
        title="Inviting Online Application Form for Joint Entrance Examination (JEE Main) 2026",
        url="https://nta.ac.in/Download/jee_main_2026.pdf"
    )
    assert cat_jee == NoticeCategory.ADMISSION_OR_ENTRANCE_EXAM

    # 8. Internal departmental recruitment or promotion
    cat_ldce = NoticeClassifier.classify(
        title="Grade 'C' Stenographers Limited Departmental Competitive Examination (LDCE) 2026",
        url="https://ssc.gov.in/notices/ldce_steno_2026.pdf"
    )
    assert cat_ldce == NoticeCategory.INTERNAL_CIRCULAR

    # 9. General administrative announcements
    cat_admin = NoticeClassifier.classify(
        title="Relocation of NTA Office from Okhla to New Administrative Building",
        url="https://nta.ac.in/Download/office_relocation.pdf"
    )
    assert cat_admin == NoticeCategory.ADMINISTRATIVE_ANNOUNCEMENT


# =========================================================================
# 2. Parent Notice Linking Tests
# =========================================================================

def test_parent_notice_linking_unambiguous(readiness_db):
    """Corrigendum with exact notice number or clear exam title links to parent recruitment notice."""
    with get_db(readiness_db) as conn:
        # Seed parent recruitment notice
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_parent_je', 'src_ssc', 'Staff Selection Commission', 'JE/2026',
                'Junior Engineer (Civil, Mechanical, Electrical) Examination 2026',
                'https://ssc.gov.in/notices/je_2026_advt.pdf',
                'Recruitment', 'Central', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED',
                '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z'
            )
            """
        )

        # 1. Exact notice number match
        parent_id, rel_type, rel_conf, notes = NoticeClassifier.link_to_parent_notice(
            notice_id="not_corr_1",
            source_id="src_ssc",
            title="Corrigendum to Junior Engineer Examination",
            notice_number="JE/2026",
            category=NoticeCategory.CORRIGENDUM,
            conn=conn,
        )
        assert parent_id == "not_parent_je"
        assert rel_type == "CORRIGENDUM"
        assert rel_conf >= 0.95
        assert "Exact notice number match" in notes

        # 2. Title keyword match (no notice number)
        parent_id2, rel_type2, rel_conf2, notes2 = NoticeClassifier.link_to_parent_notice(
            notice_id="not_addendum_1",
            source_id="src_ssc",
            title="Addendum: Additional Vacancies in Junior Engineer Examination 2026",
            notice_number="",
            category=NoticeCategory.RECRUITMENT_ADDENDUM,
            conn=conn,
        )
        assert parent_id2 == "not_parent_je"
        assert rel_type2 == "RECRUITMENT_ADDENDUM"
        assert rel_conf2 >= 0.70
        assert "Unambiguous title overlap" in notes2


def test_parent_notice_linking_ambiguous_flags_human_review(readiness_db):
    """When multiple parents match, linking must NOT guess; flags for human review."""
    with get_db(readiness_db) as conn:
        # Seed two distinct candidate parent notices for same authority
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES
            ('parent_app_cbi', 'src_upsc', 'Union Public Service Commission', '01/2026',
             '05 Posts of Assistant Public Prosecutor in CBI', 'https://upsc.gov.in/cbi_app.pdf',
             'Recruitment', 'Central', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED', '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z'),
            ('parent_app_delhi', 'src_upsc', 'Union Public Service Commission', '02/2026',
             '140 Posts of Assistant Public Prosecutor in Directorate of Prosecution Delhi', 'https://upsc.gov.in/delhi_app.pdf',
             'Recruitment', 'Central', 'RECRUITMENT_NOTIFICATION', 'DISCOVERED', '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z')
            """
        )

        # Ambiguous title with no notice number: matches both "Assistant Public Prosecutor" notices
        parent_id, rel_type, rel_conf, notes = NoticeClassifier.link_to_parent_notice(
            notice_id="not_addendum_ambiguous",
            source_id="src_upsc",
            title="Addendum Notice: Assistant Public Prosecutor Post Recruitment",
            notice_number="",
            category=NoticeCategory.RECRUITMENT_ADDENDUM,
            conn=conn,
        )
        # Must NOT silently bind to either
        assert parent_id is None
        assert "AMBIGUOUS_PARENT_LINK" in notes

        # Verify classify_and_update flags triage_flag
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_addendum_ambiguous', 'src_upsc', 'Union Public Service Commission', '',
                'Addendum Notice: Assistant Public Prosecutor Post Recruitment',
                'https://upsc.gov.in/addendum_amb.pdf',
                'Recruitment', 'Central', 'RECRUITMENT_ADDENDUM', 'DISCOVERED',
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
                'v_amb', 'not_addendum_ambiguous', 1, 'https://upsc.gov.in/addendum_amb.pdf',
                'hash_amb', 'PDF', 'amb.pdf', 'Addendum Notice for Assistant Public Prosecutor', 1, '2026-10-29T10:00:00Z'
            )
            """
        )
        cat = NoticeClassifier.classify_and_update("not_addendum_ambiguous", conn)
        assert cat == NoticeCategory.RECRUITMENT_ADDENDUM

        row = conn.execute(
            "SELECT triage_flag, triage_notes, parent_notice_id FROM canonical_notices WHERE id = 'not_addendum_ambiguous'"
        ).fetchone()
        assert row["parent_notice_id"] is None
        assert row["triage_flag"] == "AMBIGUOUS_PARENT_LINK_FLAGGED_FOR_HUMAN_REVIEW"
        assert "AMBIGUOUS_PARENT_LINK" in row["triage_notes"]


# =========================================================================
# 3. Template Routing and QA Consistency Tests
# =========================================================================

def test_template_routing_and_qa_consistency(readiness_db):
    """Addenda and non-recruitment notices use appropriate templates and do not demand application dates."""
    writer = WritingAgent(db_path=readiness_db)
    qa_agent = QualityAssuranceAgent(db_path=readiness_db)

    # 1. Addendum notice routes to corrigendum.md.j2
    tmpl_add = writer.select_template("RECRUITMENT_ADDENDUM")
    assert tmpl_add == "corrigendum.md.j2"

    # 2. Admission notice routes to announcement.md.j2
    tmpl_adm = writer.select_template("ADMISSION_OR_ENTRANCE_EXAM")
    assert tmpl_adm == "announcement.md.j2"

    # 3. Administrative notice routes to announcement.md.j2
    tmpl_adm2 = writer.select_template("ADMINISTRATIVE_ANNOUNCEMENT")
    assert tmpl_adm2 == "announcement.md.j2"

    with get_db(readiness_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_nta_reloc', 'src_nta', 'National Testing Agency', '',
                'Relocation of NTA Office from Okhla to New Premises',
                'https://nta.ac.in/office_relocation.pdf',
                'General', 'Central', 'ADMINISTRATIVE_ANNOUNCEMENT', 'EXTRACTED',
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
                'v_reloc', 'not_nta_reloc', 1, 'https://nta.ac.in/office_relocation.pdf',
                'hash_reloc', 'PDF', 'reloc.pdf', 'Relocation of NTA office official text', 1, '2026-10-29T10:00:00Z'
            )
            """
        )

    art_id, arv_id, content_hash = writer.draft_article("not_nta_reloc")
    qa_passed, qa_score, qa_checks = qa_agent.inspect_and_evaluate(arv_id)

    # Does not fail QA for missing recruitment dates
    assert qa_passed is True
    assert qa_score >= 85.0
    assert not any(c.rule_name == "rule_recruitment_critical_dates" and not c.passed for c in qa_checks)


# =========================================================================
# 4. Scheduler Lifecycle and Concurrency Tests
# =========================================================================

def test_scheduler_lifecycle_and_duplicate_prevention(readiness_db):
    """ScanScheduler starts cleanly, prevents duplicate instances, and shuts down safely."""
    sched1 = ScanScheduler(db_path=readiness_db)
    sched1.start()

    try:
        assert sched1.is_running is True
        status = sched1.get_status()
        assert status["running"] is True
        assert status["timezone"] == "Asia/Kolkata"
        assert status["scan_hours"] == [6, 18]
        assert status["scan_minutes"] == 0
        assert status["next_run_time"] is not None

        # Attempting to start a second concurrent scheduler MUST raise SchedulerAlreadyRunningError
        sched2 = ScanScheduler(db_path=readiness_db)
        with pytest.raises(SchedulerAlreadyRunningError):
            sched2.start()

    finally:
        sched1.shutdown()
        assert sched1.is_running is False

    # After shutdown, starting a new scheduler succeeds
    sched3 = ScanScheduler(db_path=readiness_db)
    sched3.start()
    assert sched3.is_running is True
    sched3.shutdown()
    assert sched3.is_running is False


# =========================================================================
# 5. Editorial Override Governance Tests
# =========================================================================

def test_editorial_override_governance_auditing(readiness_db):
    """Overrides must record explicit waived fields and justification in approval_records and audit_events."""
    service = EditorialService(db_path=readiness_db)

    with get_db(readiness_db) as conn:
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                first_discovered_at, last_updated_at
            ) VALUES (
                'not_gov_rec', 'src_upsc', 'Union Public Service Commission', '10/2026',
                'Special Shortlist Recruitment Notice without Dates',
                'https://upsc.gov.in/special_notice.pdf',
                'Recruitment', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
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
                'v_gov', 'not_gov_rec', 1, 'https://upsc.gov.in/special_notice.pdf',
                'hash_gov', 'PDF', 'gov.pdf', 'Special notice text', 1, '2026-10-29T10:00:00Z'
            )
            """
        )
        # Seed 1 verified fact (vacancies), but missing application start/end dates
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, confidence,
                evidence_text, page_number, verified_status, created_at
            ) VALUES ('f_gov_vac', 'v_gov', 'total_vacancies', '12', 0.95, '12 posts', 1, 'VERIFIED', '2026-10-29T10:00:00Z')
            """
        )

    writer = WritingAgent(db_path=readiness_db)
    art_id, arv_id, content_hash = writer.draft_article("not_gov_rec")

    # 1. Ordinary approval must be BLOCKED
    with pytest.raises(ApprovalBlockedError):
        service.submit_decision(
            article_id=art_id,
            expected_version_id=arv_id,
            expected_content_hash=content_hash,
            decision="APPROVE",
            is_override=False,
        )

    # 2. Override with short/missing justification rejected
    with pytest.raises(EditorialSecurityError):
        service.submit_decision(
            article_id=art_id,
            expected_version_id=arv_id,
            expected_content_hash=content_hash,
            decision="APPROVE",
            is_override=True,
            override_reason="too short",
        )

    # 3. Authorized override with recorded reason succeeds
    app_res = service.submit_decision(
        article_id=art_id,
        expected_version_id=arv_id,
        expected_content_hash=content_hash,
        decision="APPROVE",
        is_override=True,
        override_reason="Shortlist notice: application window closed in initial advertisement verified.",
        editor_email="meettomar07@gmail.com",
    )
    assert app_res["decision"] == "APPROVED"
    assert app_res["is_override"] is True
    assert "application_start_date" in app_res["unverified_fields_waived"]

    # 4. Verify database persistence in approval_records
    with get_db(readiness_db) as conn:
        app_rec = conn.execute(
            "SELECT is_override, override_reason, unverified_fields_waived FROM approval_records WHERE id = ?",
            (app_res["approval_id"],),
        ).fetchone()
        assert app_rec["is_override"] == 1
        assert "Shortlist notice" in app_rec["override_reason"]
        assert "application_start_date" in app_rec["unverified_fields_waived"]

        # 5. Verify audit event
        audit_rec = conn.execute(
            "SELECT action, actor, payload_json FROM audit_events WHERE entity_id = ?",
            (app_res["approval_id"],),
        ).fetchone()
        assert audit_rec["action"] == "EDITORIAL_OVERRIDE_APPROVED"
        assert audit_rec["actor"] == "meettomar07@gmail.com"
        payload = json.loads(audit_rec["payload_json"])
        assert payload["is_override"] is True
        assert "application_start_date" in payload["unverified_fields_waived"]


def test_pilot_batch_2_dataset_integrity_and_zero_overlap():
    """Verify Pilot Batch 2 contains 15 fresh documents with 0% overlap against all 145 benchmark notices."""
    import hashlib
    manifest_p2 = Path("PILOT_BATCH_2_MANIFEST.json")
    assert manifest_p2.exists(), "PILOT_BATCH_2_MANIFEST.json missing"
    data_p2 = json.loads(manifest_p2.read_text(encoding="utf-8"))
    docs_p2 = data_p2["documents"]
    assert len(docs_p2) == 15, f"Expected 15 documents in Pilot Batch 2, got {len(docs_p2)}"

    # Check 5 authorities represented
    dist = data_p2["authorities_distribution"]
    assert dist["SSC"] == 3
    assert dist["UPSC"] == 3
    assert dist["NTA"] == 3
    assert dist["UPPSC"] == 3
    assert dist["TNPSC"] == 3

    # Load all 145 benchmark hashes
    benchmark_manifests = [
        "DEVELOPMENT_SET_MANIFEST.json",
        "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
        "GENERALIZATION_SET_MANIFEST.json",
        "NEW_VALIDATION_DATASET_MANIFEST.json",
        "PILOT_DATASET_MANIFEST.json",
        "VERIFICATION_SET_MANIFEST.json",
    ]
    restricted_hashes = set()
    for mf in benchmark_manifests:
        p = Path(mf)
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            for doc in d.get("documents", {}).values():
                if "sha256" in doc and doc["sha256"]:
                    restricted_hashes.add(doc["sha256"].lower().strip())

    assert len(restricted_hashes) == 145, f"Expected 145 unique benchmark hashes, got {len(restricted_hashes)}"

    seen_batch_hashes = set()
    for filename, doc in docs_p2.items():
        local_p = Path(doc["local_path"])
        assert local_p.exists(), f"Document file missing: {local_p}"
        actual_hash = hashlib.sha256(local_p.read_bytes()).hexdigest().lower()
        assert actual_hash == doc["sha256"].lower(), f"Manifest hash mismatch for {filename}"
        assert actual_hash not in restricted_hashes, f"COLLISION with benchmark notice in {filename}: {actual_hash}"
        assert actual_hash not in seen_batch_hashes, f"Batch internal duplicate: {filename}"
        seen_batch_hashes.add(actual_hash)

