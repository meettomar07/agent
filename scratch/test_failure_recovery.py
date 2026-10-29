"""Verify timeouts, retries, source failures, partial failures, and recovery."""

import uuid
from unittest.mock import MagicMock
import httpx
from pathlib import Path

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import SourceRegistryService, seed_sources_if_empty
from testkart_intelligence.discovery.fetcher import SafeFetcher
from testkart_intelligence.discovery.engine import DiscoveryEngine

test_db = settings.BASE_DIR / "data" / "failure_recovery_test.db"
if test_db.exists():
    test_db.unlink()
init_db(test_db)
with get_db(test_db) as conn:
    seed_sources_if_empty(conn)

print("=== 1. SIMULATE PARTIAL FAILURE (TIMEOUT ON UPSC, SUCCESS ON SSC) ===")

mock_client = MagicMock()

def mock_get(url, **kwargs):
    if "upsc.gov.in" in url:
        raise httpx.ReadTimeout("Connection timed out after 25.0s")
    
    resp = MagicMock()
    resp.is_redirect = False
    resp.raise_for_status = MagicMock()
    resp.content = b"<html><body><table><tr><td>No updates</td></tr></table></body></html>"
    resp.headers = {"Content-Type": "text/html"}
    return resp

mock_client.get = mock_get

fetcher = SafeFetcher(client=mock_client, rate_limit_delay=0.0)
engine = DiscoveryEngine(db_path=test_db, fetcher=fetcher)

# Run scan across all sources (with UPSC failing and others succeeding)
result = engine.run_scan(scan_type="MANUAL")
print(f"Scan Run ID: {result['scan_id']}")
print(f"Scan Status: {result['status']}")
print(f"Sources Checked: {result['sources_checked']}")
print(f"Errors Count: {result['errors_count']}")
print(f"Error Summary: {result['error_summary']}")

assert result["errors_count"] == 1
assert any("Connection timed out" in s for s in result["error_summary"])
assert result["status"] == "COMPLETED"

with get_db(test_db) as conn:
    # Check source logs
    logs = conn.execute(
        "SELECT s.code, ssl.status, ssl.error_message FROM scan_source_logs ssl JOIN official_sources s ON ssl.source_id = s.id WHERE ssl.scan_run_id = ?",
        (result["scan_id"],)
    ).fetchall()
    print("\nSource Logs for Run:")
    for l in logs:
        print(f"  [{l['code']}] Status: {l['status']}, Error: {l['error_message']}")

    # Check UPSC consecutive failures
    upsc_src = conn.execute("SELECT consecutive_failures, last_error FROM official_sources WHERE code = 'UPSC'").fetchone()
    print(f"\nUPSC Consecutive Failures: {upsc_src['consecutive_failures']}")
    assert upsc_src["consecutive_failures"] == 1

print("Partial failure logging: PASSED")

print("\n=== 2. SIMULATE SOURCE RECOVERY ON NEXT SCAN ===")
# UPSC now recovers
def mock_get_recovered(url, **kwargs):
    resp = MagicMock()
    resp.is_redirect = False
    resp.raise_for_status = MagicMock()
    resp.content = b"<html><body><table><tr><td>Normal listing</td></tr></table></body></html>"
    resp.headers = {"Content-Type": "text/html"}
    return resp

mock_client.get = mock_get_recovered

result_recovered = engine.run_scan(scan_type="MANUAL")
print(f"Recovered Scan Run ID: {result_recovered['scan_id']}")
print(f"Recovered Scan Status: {result_recovered['status']}")
print(f"Errors Count: {result_recovered['errors_count']}")
assert result_recovered["errors_count"] == 0
assert result_recovered["status"] == "COMPLETED"

with get_db(test_db) as conn:
    upsc_recovered = conn.execute("SELECT consecutive_failures, last_error, last_success_at FROM official_sources WHERE code = 'UPSC'").fetchone()
    print(f"UPSC Consecutive Failures after recovery: {upsc_recovered['consecutive_failures']}")
    print(f"UPSC Last Error: {upsc_recovered['last_error']}")
    print(f"UPSC Last Success At: {upsc_recovered['last_success_at']}")
    assert upsc_recovered["consecutive_failures"] == 0
    assert upsc_recovered["last_error"] is None

print("Source recovery verification: PASSED")

print("\n=== 3. VERIFY SUCCESS_NO_NEW ON EMPTY SCAN ===")
with get_db(test_db) as conn:
    empty_logs = conn.execute(
        "SELECT s.code, ssl.status, ssl.notices_found_count FROM scan_source_logs ssl JOIN official_sources s ON ssl.source_id = s.id WHERE ssl.scan_run_id = ?",
        (result_recovered["scan_id"],)
    ).fetchall()
    print("Source statuses on empty scan:")
    for el in empty_logs:
        print(f"  [{el['code']}] Status: {el['status']}, Notices Found: {el['notices_found_count']}")
        assert el["status"] == "SUCCESS_NO_NEW"

print("Empty scan vs failed source distinction: PASSED")

if test_db.exists():
    test_db.unlink()
