import sqlite3
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timezone

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.editorial.service import EditorialService, StaleVersionConflictError
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.publishing.mock_publisher import MockPublisher, MockPublishingError


def run_controlled_approval_invalidation_test(tmp_db: Path):
    init_db(tmp_db)
    now_iso = datetime.now(timezone.utc).isoformat()
    service = EditorialService(db_path=tmp_db)
    writer = WritingAgent(db_path=tmp_db)
    qa = QualityAssuranceAgent(db_path=tmp_db)
    publisher = MockPublisher(db_path=tmp_db)

    # 1. Setup Source and Canonical Notice
    with get_db(tmp_db) as conn:
        conn.execute(
            """
            INSERT INTO official_sources (
                id, code, name, category, state, official_domain, listing_url,
                retrieval_method, verification_status, enabled, consecutive_failures,
                created_at, updated_at
            ) VALUES ('src_test', 'TEST_SRC', 'Test Commission', 'Central', 'Central',
                      'test.gov.in', 'https://test.gov.in/notices', 'html_scrape', 'VERIFIED', 1, 0,
                      ?, ?)
            """,
            (now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, classification, status,
                published_date, first_discovered_at, last_updated_at
            ) VALUES ('not_rev_test', 'src_test', 'Test Commission', '01/2026',
                      'Assistant Engineer Examination 2026', 'https://test.gov.in/ae-2026.pdf',
                      'Central', 'Central', 'RECRUITMENT_NOTIFICATION', 'EXTRACTED',
                      '2026-10-24', ?, ?)
            """,
            (now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES ('nv_1', 'not_rev_test', 1, 'https://test.gov.in/ae-2026.pdf',
                      'hash_nv1', 'PDF', 'mock.pdf', 'Assistant Engineer Examination 2026', 1, ?)
            """,
            (now_iso,),
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, evidence_text, page_number, confidence, verified_status, created_at
            ) VALUES
            ('f1', 'nv_1', 'recruiting_authority', 'Test Commission', 'Test Commission', 1, 1.0, 'VERIFIED', ?),
            ('f2', 'nv_1', 'official_source_url', 'https://test.gov.in/ae-2026.pdf', 'https://test.gov.in', 1, 1.0, 'VERIFIED', ?),
            ('f3', 'nv_1', 'application_start_date', '01.11.2026', '01.11.2026', 1, 0.95, 'VERIFIED', ?),
            ('f4', 'nv_1', 'application_end_date', '30.11.2026', '30.11.2026', 1, 0.95, 'VERIFIED', ?),
            ('f5', 'nv_1', 'total_vacancies', '150', '150 posts', 1, 0.95, 'VERIFIED', ?)
            """,
            (now_iso, now_iso, now_iso, now_iso, now_iso),
        )

    # 2. Draft Article Version 1
    art_id, arv1_id, hash_v1 = writer.draft_article("not_rev_test")
    passed, score, _ = qa.inspect_and_evaluate(arv1_id)
    assert passed is True, f"QA failed with score {score}"

    print(f"Drafted Version 1: {arv1_id} (hash: {hash_v1[:12]}), QA Passed: {passed}")

    # 3. Approve Version 1 explicitly in local review workflow
    dec_result = service.submit_decision(
        article_id=art_id,
        expected_version_id=arv1_id,
        expected_content_hash=hash_v1,
        decision="APPROVE",
        editor_email="meettomar07@gmail.com",
        notes="All dates and facts verified against official AE-2026 PDF.",
    )
    assert dec_result["decision"] == "APPROVED"
    print(f"Explicitly Approved Version 1: decision={dec_result['decision']}")

    # Verify article status is now APPROVED
    with get_db(tmp_db) as conn:
        art_row = conn.execute("SELECT status, current_version_id FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        assert art_row["status"] == "APPROVED"
        assert art_row["current_version_id"] == arv1_id

    # 4. Simulate Notice Revision (e.g. deadline extended or vacancies revised)
    print("\nSimulating official corrigendum / revision...")
    with get_db(tmp_db) as conn:
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, raw_text, page_count, retrieved_at
            ) VALUES ('nv_2', 'not_rev_test', 2, 'https://test.gov.in/ae-2026-corrigendum.pdf',
                      'hash_nv2', 'PDF', 'mock2.pdf', 'Corrigendum: Application deadline extended to 15.12.2026', 1, ?)
            """,
            (now_iso,),
        )
        conn.execute(
            """
            INSERT INTO extracted_facts (
                id, notice_version_id, fact_key, fact_value, evidence_text, page_number, confidence, verified_status, created_at
            ) VALUES
            ('f1_v2', 'nv_2', 'recruiting_authority', 'Test Commission', 'Test Commission', 1, 1.0, 'VERIFIED', ?),
            ('f2_v2', 'nv_2', 'official_source_url', 'https://test.gov.in/ae-2026-corrigendum.pdf', 'https://test.gov.in', 1, 1.0, 'VERIFIED', ?),
            ('f3_v2', 'nv_2', 'application_start_date', '01.11.2026', '01.11.2026', 1, 0.95, 'VERIFIED', ?),
            ('f4_v2', 'nv_2', 'application_end_date', '15.12.2026', '15.12.2026 (Extended)', 1, 0.95, 'VERIFIED', ?),
            ('f5_v2', 'nv_2', 'total_vacancies', '180', '180 posts', 1, 0.95, 'VERIFIED', ?)
            """,
            (now_iso, now_iso, now_iso, now_iso, now_iso),
        )

    # Regenerate article draft for the revised notice version
    art_id2, arv2_id, hash_v2 = writer.draft_article("not_rev_test", notice_version_id="nv_2")
    assert art_id2 == art_id
    assert arv2_id != arv1_id
    assert hash_v2 != hash_v1
    print(f"Regenerated Version 2: {arv2_id} (hash: {hash_v2[:12]})")

    # 5. Confirm old approval CANNOT authorize new version
    with get_db(tmp_db) as conn:
        art_row_after = conn.execute("SELECT status, current_version_id FROM blog_articles WHERE id = ?", (art_id,)).fetchone()
        print(f"Article status reset to: {art_row_after['status']} (current_version: {art_row_after['current_version_id']})")
        assert art_row_after["status"] == "DRAFT", "Article status must reset to DRAFT upon revision!"

        # Check approval records
        v1_approvals = conn.execute("SELECT id, article_version_id, content_hash, status FROM approval_records WHERE article_version_id = ?", (arv1_id,)).fetchall()
        print("Version 1 Approval Records:")
        for r in v1_approvals:
            print(f"  ID: {r['id']}, Bound Version: {r['article_version_id']}, Hash: {r['content_hash'][:12]}, Status: {r['status']}")

        v2_approvals = conn.execute("SELECT * FROM approval_records WHERE article_version_id = ?", (arv2_id,)).fetchall()
        print(f"Version 2 Approval Records count: {len(v2_approvals)} (Must be 0)")
        assert len(v2_approvals) == 0, "New version must have 0 approvals!"

    # 6. Verify MockPublisher strictly BLOCKS publication of Version 2 using old approval
    v1_appr_id = v1_approvals[0]["id"]
    try:
        publisher.publish(
            article_version_id=arv2_id,
            content_hash=hash_v2,
            approval_record_id=v1_appr_id,
        )
        assert False, "Publication of Version 2 with Version 1 approval should have failed!"
    except MockPublishingError as e:
        print(f"Publication of Version 2 with old approval correctly blocked: {e}")

    # 7. Verify stale decision submission on old version is rejected
    try:
        service.submit_decision(
            article_id=art_id,
            expected_version_id=arv1_id,
            expected_content_hash=hash_v1,
            decision="APPROVE",
            editor_email="meettomar07@gmail.com",
        )
        assert False, "Submitting decision for stale version should have raised StaleVersionConflictError!"
    except StaleVersionConflictError as e:
        print(f"Stale version approval attempt correctly rejected: {e}")

    # 8. Verify audit trail records exact version hash and decision
    with get_db(tmp_db) as conn:
        audit_events = conn.execute("SELECT entity_type, entity_id, action, actor, payload_json, timestamp FROM audit_events ORDER BY timestamp ASC").fetchall()
        print(f"\nAudit Trail Events ({len(audit_events)} total):")
        for ae in audit_events:
            print(f"  [{ae['action']}] actor={ae['actor']} entity={ae['entity_type']}:{ae['entity_id']} payload={ae['payload_json']}")

    print("\nSUCCESS: Approval invalidation fully validated under controlled local test.")


if __name__ == "__main__":
    test_db_path = Path("scratch/test_invalidation.db")
    if test_db_path.exists():
        test_db_path.unlink()
    run_controlled_approval_invalidation_test(test_db_path)
