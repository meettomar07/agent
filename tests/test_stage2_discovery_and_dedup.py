"""Unit tests for Stage 2: Fetcher, Parser, Deduplication, and Discovery Engine."""

import pytest
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock
import httpx

from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import SourceRegistryService, seed_sources_if_empty
from testkart_intelligence.discovery.fetcher import SafeFetcher, FetchError
from testkart_intelligence.discovery.parser import ListingParser, normalize_notice_url
from testkart_intelligence.discovery.deduplication import DeduplicationEngine, MatchType
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.security.allowlist import SecurityValidationError


SAMPLE_HTML_TABLE = """
<!DOCTYPE html>
<html>
<body>
  <table>
    <tr><th>Date</th><th>Notification Title</th><th>Document</th></tr>
    <tr>
      <td>24/10/2026</td>
      <td>Combined Geo-Scientist Examination 2026 (Advt. No. 02/2026-GEOL)</td>
      <td><a href="/examinations/geoscientist-2026.pdf">Download Notice (PDF)</a></td>
    </tr>
    <tr>
      <td>22/10/2026</td>
      <td>Engineering Services Examination 2026 Notice (Advt. No. 01/2026-ENGG)</td>
      <td><a href="/examinations/ese-2026.pdf">Notice PDF</a></td>
    </tr>
    <tr>
      <td>20/10/2026</td>
      <td>External Unofficial Coaching Guide</td>
      <td><a href="https://sarkariresults.fake/guide.pdf">Fake Guide</a></td>
    </tr>
  </table>
  <footer>
    <a href="/home">Home</a>
    <a href="/contact">Contact Us</a>
    <a href="/rti">RTI</a>
  </footer>
</body>
</html>
"""


@pytest.fixture
def test_db(tmp_path: Path):
    db_file = tmp_path / "test_stage2.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        seed_sources_if_empty(conn)
    return db_file


def test_listing_parser_table_and_filtering():
    """Verify table link extraction, advt number detection, and non-official link rejection."""
    candidates = ListingParser.parse_listing(SAMPLE_HTML_TABLE, "https://upsc.gov.in/notices")
    assert len(candidates) == 2

    first = candidates[0]
    assert first["url"] == "https://upsc.gov.in/examinations/geoscientist-2026.pdf"
    assert first["document_type"] == "PDF"
    assert first["notice_number"] == "02/2026-GEOL"

    second = candidates[1]
    assert second["url"] == "https://upsc.gov.in/examinations/ese-2026.pdf"
    assert second["notice_number"] == "01/2026-ENGG"

    # Verify that the fake/aggregator link was completely discarded
    urls = [c["url"] for c in candidates]
    assert not any("sarkariresults.fake" in u for u in urls)
    # Verify navigation links were discarded
    assert not any("contact" in u or "rti" in u for u in urls)


def test_url_normalization():
    """Verify URL normalization removes fragments and tracking parameters."""
    norm = normalize_notice_url("notice.pdf#page=1", "https://upsc.gov.in/active/")
    assert norm == "https://upsc.gov.in/active/notice.pdf"

    norm_query = normalize_notice_url("notice.pdf?utm_source=fb&id=123", "https://upsc.gov.in/active/")
    assert norm_query == "https://upsc.gov.in/active/notice.pdf?id=123"


def test_deduplication_lifecycle(test_db: Path):
    """Test candidate lifecycle: NEW -> UNCHANGED -> REVISION (when hash changes)."""
    with get_db(test_db) as conn:
        dedup = DeduplicationEngine(conn)

        # 1. New candidate
        match, can_id, v_num = dedup.evaluate_candidate(
            source_id="src_upsc",
            normalized_url="https://upsc.gov.in/notices/exam1.pdf",
            notice_number="01/2026",
            title="Exam 1 Notification",
        )
        assert match == MatchType.NEW
        assert can_id is None

        # Insert notice and initial version
        notice_id = "not_test1"
        conn.execute(
            """
            INSERT INTO canonical_notices (
                id, source_id, authority_name, notice_number, title,
                normalized_url, category, state, status, first_discovered_at, last_updated_at
            ) VALUES (?, 'src_upsc', 'UPSC', '01/2026', 'Exam 1 Notification',
                      'https://upsc.gov.in/notices/exam1.pdf', 'Central', 'Central', 'DISCOVERED', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """,
            (notice_id,),
        )
        conn.execute(
            """
            INSERT INTO notice_versions (
                id, notice_id, version_number, document_url, document_hash,
                document_type, storage_path, retrieved_at
            ) VALUES ('ver_1', ?, 1, 'https://upsc.gov.in/notices/exam1.pdf', 'hash_aaa', 'PDF', '/tmp/doc.pdf', '2026-10-24T00:00:00Z')
            """,
            (notice_id,),
        )

        # 2. Check candidate with identical hash -> UNCHANGED
        match2, can_id2, v_num2 = dedup.evaluate_candidate(
            source_id="src_upsc",
            normalized_url="https://upsc.gov.in/notices/exam1.pdf",
            notice_number="01/2026",
            new_doc_hash="hash_aaa",
        )
        assert match2 == MatchType.UNCHANGED
        assert can_id2 == notice_id
        assert v_num2 == 1

        # 3. Check candidate with new hash (corrigendum / updated doc) -> REVISION
        match3, can_id3, v_num3 = dedup.evaluate_candidate(
            source_id="src_upsc",
            normalized_url="https://upsc.gov.in/notices/exam1.pdf",
            notice_number="01/2026",
            new_doc_hash="hash_bbb",
        )
        assert match3 == MatchType.REVISION
        assert can_id3 == notice_id
        assert v_num3 == 1


def test_discovery_engine_success_and_empty_distinction(test_db: Path):
    """Verify DiscoveryEngine distinguishes SUCCESS_NEW from SUCCESS_NO_NEW and logs errors."""
    mock_client = MagicMock()

    # Source 1 (UPSC): Returns valid table with 2 notices
    resp_upsc = MagicMock()
    resp_upsc.is_redirect = False
    resp_upsc.content = SAMPLE_HTML_TABLE.encode("utf-8")
    resp_upsc.headers = {"Content-Type": "text/html"}
    resp_upsc.raise_for_status = MagicMock()

    # Source 2 (SSC): Returns empty notice board (no notices)
    resp_empty = MagicMock()
    resp_empty.is_redirect = False
    resp_empty.content = b"<html><body><h3>Notice Board</h3><p>No current active notifications.</p></body></html>"
    resp_empty.headers = {"Content-Type": "text/html"}
    resp_empty.raise_for_status = MagicMock()

    # Dispatch responses based on URL
    def mock_get(url, **kwargs):
        if "upsc.gov.in" in url:
            return resp_upsc
        elif "ssc.gov.in" in url:
            return resp_empty
        else:
            raise httpx.ConnectTimeout("Connection timeout to server")

    mock_client.get = mock_get

    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)
    engine = DiscoveryEngine(db_path=test_db, fetcher=fetcher)

    # Disable all sources except UPSC and SSC
    service = SourceRegistryService(test_db)
    for s in service.list_sources():
        if s["code"] not in ("UPSC", "SSC"):
            service.set_enabled(s["code"], False)

    # Run scan
    result = engine.run_scan(scan_type="MANUAL")
    assert result["status"] == "COMPLETED"
    assert result["sources_checked"] == 2
    assert result["notices_found"] == 2
    assert result["errors_count"] == 0

    # Inspect scan_source_logs
    with get_db(test_db) as conn:
        logs = conn.execute("SELECT * FROM scan_source_logs WHERE scan_run_id = ?", (result["scan_id"],)).fetchall()
        statuses = {l["source_id"]: l["status"] for l in logs}

        # UPSC had 2 new notices -> SUCCESS_NEW
        assert statuses["src_upsc"] == "SUCCESS_NEW"
        # SSC had 0 notices but successful HTTP 200 -> SUCCESS_NO_NEW
        assert statuses["src_ssc"] == "SUCCESS_NO_NEW"


def test_discovery_engine_failed_source_logging(test_db: Path):
    """Verify failed source checks log FAILED status and record error details."""
    mock_client = MagicMock()

    def mock_get(url, **kwargs):
        raise httpx.HTTPStatusError("503 Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503))

    mock_client.get = mock_get

    fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0, max_retries=1)
    engine = DiscoveryEngine(db_path=test_db, fetcher=fetcher)

    service = SourceRegistryService(test_db)
    for s in service.list_sources():
        if s["code"] != "UPSC":
            service.set_enabled(s["code"], False)

    result = engine.run_scan(scan_type="MANUAL")
    assert result["errors_count"] == 1
    assert result["notices_found"] == 0
    assert result["status"] == "FAILED"

    # Verify source registry tracks failure
    upsc_src = service.get_source_by_code("UPSC")
    assert upsc_src["consecutive_failures"] >= 1
    assert upsc_src["last_error"] is not None
