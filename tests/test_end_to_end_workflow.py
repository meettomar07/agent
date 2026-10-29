"""End-to-End Test: Full Discovery-to-Approval-and-Mock-Publish Pipeline."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
import httpx
import pymupdf

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import SourceRegistryService, seed_sources_if_empty
from testkart_intelligence.discovery.fetcher import SafeFetcher
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.extraction.verifier import VerificationAgent
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.security.approvals import ApprovalService
from testkart_intelligence.publishing.mock_publisher import MockPublisher
from testkart_intelligence.config import settings


def create_sample_pdf_bytes(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=12)
    b = doc.tobytes()
    doc.close()
    return b


def test_end_to_end_pipeline(tmp_path: Path):
    """Execute end-to-end multi-agent lifecycle:

    1. Seed official sources
    2. Discovery scan detects notice
    3. Document ingestion & fact extraction
    4. Classification
    5. Draft generation
    6. Quality assurance checks
    7. Human approval token & explicit decision
    8. Mock publishing & idempotency
    9. Complete audit trail verification
    """
    test_db = tmp_path / "e2e.db"
    init_db(test_db)
    with get_db(test_db) as conn:
        seed_sources_if_empty(conn)

    # Prepare Mock HTTP responses for UPSC
    html_listing = """
    <html>
      <body>
        <table>
          <tr>
            <td>24/10/2026</td>
            <td>Central Armed Police Forces (Assistant Commandants) Examination 2026</td>
            <td><a href="/capf-2026-notice.pdf">Download Notice PDF</a></td>
          </tr>
        </table>
      </body>
    </html>
    """

    pdf_text = (
        "UNION PUBLIC SERVICE COMMISSION\n"
        "Notice No. 08/2026-CAPF\n"
        "Central Armed Police Forces (Assistant Commandants) Examination 2026\n"
        "Total Vacancies: 506\n"
        "Opening Date: 20/04/2026\n"
        "Closing Date: 14/05/2026\n"
        "Date of Examination: 02/08/2026\n"
        "Age limit: 20 to 25 years\n"
        "Educational Qualification: Bachelor's Degree in any discipline\n"
        "Application Fee: Rs. 200, Female/SC/ST candidates are exempted\n"
        "Selection Process: Written Examination, Physical Standards/Efficiency Tests, Interview\n"
    )
    pdf_bytes = create_sample_pdf_bytes(pdf_text)

    mock_client = MagicMock()

    def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.is_redirect = False
        resp.raise_for_status = MagicMock()
        if url.endswith(".pdf"):
            resp.content = pdf_bytes
            resp.headers = {"Content-Type": "application/pdf"}
        else:
            resp.content = html_listing.encode("utf-8")
            resp.headers = {"Content-Type": "text/html"}
        return resp

    mock_client.get = mock_get

    # Step 1: Run Discovery Engine
    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)
    engine = DiscoveryEngine(db_path=test_db, fetcher=fetcher)
    scan_result = engine.run_scan(scan_type="MANUAL", source_code="UPSC")

    assert scan_result["status"] == "COMPLETED"
    assert scan_result["notices_found"] == 1

    # Fetch discovered canonical notice
    with get_db(test_db) as conn:
        notice = conn.execute("SELECT * FROM canonical_notices WHERE source_id = 'src_upsc'").fetchone()
        assert notice is not None
        notice_id = notice["id"]
        doc_url = notice["normalized_url"]

    # Step 2: Fetch Document & Verify Facts
    doc_bytes, c_type, final_url, _ = fetcher.fetch(doc_url)
    verifier = VerificationAgent(db_path=test_db)
    v_id, facts = verifier.process_and_verify_document(
        notice_id=notice_id,
        doc_bytes=doc_bytes,
        doc_url=doc_url,
        content_type=c_type,
    )
    assert v_id.startswith("ver_")

    fact_map = {f.key: f for f in facts}
    assert fact_map["total_vacancies"].value == "506"
    assert fact_map["notice_number"].value == "08/2026-CAPF"
    assert fact_map["application_start_date"].value == "20/04/2026"
    assert fact_map["application_end_date"].value == "14/05/2026"

    # Step 3: Classify Notice
    with get_db(test_db) as conn:
        category = NoticeClassifier.classify_and_update(notice_id, conn)
    assert category == NoticeCategory.RECRUITMENT_NOTIFICATION

    # Step 4: Generate Blog Draft
    writer = WritingAgent(db_path=test_db)
    art_id, art_v_id, content_hash = writer.draft_article(notice_id=notice_id)

    # Step 5: Automated Quality Assurance
    qa = QualityAssuranceAgent(db_path=test_db)
    qa_passed, qa_score, qa_checks = qa.inspect_and_evaluate(art_v_id)
    assert qa_passed is True
    assert qa_score >= 85.0

    # Step 6: Approval Request Token
    approvals = ApprovalService(db_path=test_db)
    appr_id, raw_token = approvals.create_approval_request(
        article_version_id=art_v_id,
        reviewer_email="meettomar07@gmail.com",
    )
    assert appr_id.startswith("appr_")

    # Step 7: Explicit Human Approval
    dec_result = approvals.decide_approval(
        raw_token=raw_token,
        decision="APPROVED",
        decision_notes="Confirmed against official UPSC PDF Gazette",
        client_ip="127.0.0.1",
    )
    assert dec_result["decision"] == "APPROVED"

    # Step 8: Mock Publication
    publisher = MockPublisher(db_path=test_db)
    pub_result = publisher.publish(
        article_version_id=art_v_id,
        content_hash=content_hash,
        approval_record_id=appr_id,
    )
    assert pub_result["status"] == "COMPLETED"
    assert pub_result["is_mock"] is True
    assert "https://mock.testkart.local/blog/" in pub_result["published_url"]

    # Step 9: Verify Complete Audit Trail
    with get_db(test_db) as conn:
        audit_rows = conn.execute("SELECT action FROM audit_events ORDER BY timestamp").fetchall()
        actions = [r["action"] for r in audit_rows]

        assert "APPROVAL_REQUEST_CREATED" in actions
        assert "DECISION_APPROVED" in actions
        assert "MOCK_PUBLISHED" in actions
