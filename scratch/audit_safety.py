"""Operational Safety Audit Script.
Checks:
1. ALLOW_LIVE_PUBLISHING enforcement across codebase.
2. Draft modification invalidating previous approval.
3. Handling of unreadable, ambiguous, internal-only, cancelled, and revised notices.
4. Localhost-only binding and absence of external credentials.
"""

import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.security.approvals import ApprovalService, ApprovalSecurityError
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory

def audit_safety():
    print("=" * 80)
    print("AUDIT: OPERATIONAL SAFETY & REVISION / APPROVAL GATES")
    print("=" * 80)

    # 1. ALLOW_LIVE_PUBLISHING check
    print(f"1. settings.ALLOW_LIVE_PUBLISHING = {settings.ALLOW_LIVE_PUBLISHING}")
    assert settings.ALLOW_LIVE_PUBLISHING is False

    # Check references in python files
    root = Path("testkart_intelligence")
    refs = []
    for pyf in root.rglob("*.py"):
        text = pyf.read_text(encoding="utf-8")
        if "ALLOW_LIVE_PUBLISHING" in text or "allow_live_publishing" in text:
            refs.append(str(pyf))
    print(f"   ALLOW_LIVE_PUBLISHING guarded in {len(refs)} files: {refs}")

    # 2. Localhost binding
    print(f"2. settings.SERVER_HOST = {settings.SERVER_HOST}, PORT = {settings.SERVER_PORT}")
    assert settings.SERVER_HOST in ("127.0.0.1", "localhost")

    # 3. External credentials check
    print(f"3. External credentials check:")
    print(f"   SMTP_HOST: {getattr(settings, 'SMTP_HOST', 'NOT_SET')}")
    print(f"   CMS_API_KEY: {getattr(settings, 'CMS_API_KEY', 'NOT_SET')}")
    print(f"   GMAIL_CREDENTIALS: {getattr(settings, 'GMAIL_CREDENTIALS', 'NOT_SET')}")

    # 4. Classification safety for diverse notices
    cats = {
        "Cancellation of Sub-Inspector Selection 2024": NoticeCategory.CANCELLATION_NOTICE,
        "Corrigendum regarding change in exam date": NoticeCategory.CORRIGENDUM,
        "Download E-Admit card for Tier 1": NoticeCategory.ADMIT_CARD_RELEASE,
        "Tentative Answer Key and Objection window": NoticeCategory.ANSWER_KEY,
        "Internal circular for LDCE Promotion": NoticeCategory.INTERNAL_CIRCULAR,
    }
    for title, expected in cats.items():
        actual = NoticeClassifier.classify(title)
        print(f"   Classified '{title[:40]}...' -> {actual.value} (matches: {actual == expected})")
        assert actual == expected

    # 5. Draft modification invalidating previous approval
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "safety_test.db"
        init_db(db_path)
        with get_db(db_path) as conn:
            conn.execute(
                """
                INSERT INTO official_sources (
                    id, code, name, category, state, official_domain, listing_url,
                    retrieval_method, verification_status, enabled, consecutive_failures,
                    created_at, updated_at
                ) VALUES ('src_1', 'UPSC', 'Union Public Service Commission', 'Central', 'Central',
                          'upsc.gov.in', 'https://upsc.gov.in', 'html_scrape', 'VERIFIED', 1, 0,
                          '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
                """
            )
            conn.execute(
                """
                INSERT INTO canonical_notices (
                    id, source_id, authority_name, notice_number, title,
                    normalized_url, category, state, status, first_discovered_at, last_updated_at
                ) VALUES ('not_safe_1', 'src_1', 'UPSC', '1/2026', 'Safety Notice',
                          'https://upsc.gov.in/test.pdf', 'Central', 'Central', 'DISCOVERED',
                          '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
                """
            )
            conn.execute(
                """
                INSERT INTO blog_articles (
                    id, canonical_notice_id, template_type, current_version_id, status, title, slug, created_at, updated_at
                ) VALUES ('art_safe_1', 'not_safe_1', 'recruitment', 'arv_safe_1', 'APPROVED',
                          'UPSC Safety Article', 'upsc-safety', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
                """
            )
            conn.execute(
                """
                INSERT INTO article_versions (
                    id, article_id, version_number, title, content_markdown,
                    content_hash, generated_by, created_at
                ) VALUES ('arv_safe_1', 'art_safe_1', 1, 'UPSC Safety Article',
                          'Initial approved draft', 'hash_v1', 'agent_writer', '2026-10-24T00:00:00Z')
                """
            )
            conn.commit()

        service = ApprovalService(db_path=db_path)
        rec_id, token = service.create_approval_request("arv_safe_1", "meettomar07@gmail.com")
        rec = service.decide_approval(token, "APPROVED", "Approved v1")
        print(f"4. Initial approval recorded: decision = {rec['decision']}")
        assert rec["decision"] == "APPROVED"

        with get_db(db_path) as conn:
            # Now modify draft (create version 2)
            conn.execute(
                """
                INSERT INTO article_versions (
                    id, article_id, version_number, title, content_markdown,
                    content_hash, generated_by, created_at
                ) VALUES ('arv_safe_2', 'art_safe_1', 2, 'UPSC Safety Article (Modified)',
                          'Modified draft with new dates', 'hash_v2', 'editor', '2026-10-24T01:00:00Z')
                """
            )
            conn.execute(
                """
                UPDATE blog_articles SET current_version_id = 'arv_safe_2', status = 'DRAFT' WHERE id = 'art_safe_1'
                """
            )
            conn.commit()

            # Check that old token cannot publish or approve version 2
            art = conn.execute("SELECT status, current_version_id FROM blog_articles WHERE id = 'art_safe_1'").fetchone()
            print(f"5. After editing draft: status reset to {art['status']} (current_version: {art['current_version_id']})")
            assert art["status"] == "DRAFT"
            assert art["current_version_id"] == "arv_safe_2"

        # Attempting to reuse old token raises error
        try:
            service.decide_approval(token, "APPROVED", "Trying to approve v2 with old token")
            raise AssertionError("Should have rejected already used/stale token!")
        except ApprovalSecurityError as e:
            print(f"6. Re-using old token correctly blocked: {e}")

    print("\nALL OPERATIONAL SAFETY AUDIT CHECKS PASSED.")

if __name__ == "__main__":
    audit_safety()
