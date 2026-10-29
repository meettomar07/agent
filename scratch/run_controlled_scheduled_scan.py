from testkart_intelligence.scheduler.job_runner import ScanScheduler
import sqlite3

scheduler = ScanScheduler()
print("Executing controlled scheduled scan job...")
scheduler.scan_job()

conn = sqlite3.connect("data/testkart.db")
c = conn.cursor()
last_run = c.execute("SELECT id, scan_type, status, started_at, completed_at, sources_checked, notices_found, errors_count FROM scan_runs ORDER BY started_at DESC LIMIT 1").fetchone()
print(f"Latest Scan Run: {last_run}")

total_canonical = c.execute("SELECT count(*) FROM canonical_notices").fetchone()[0]
print(f"Total Canonical Notices: {total_canonical}")
assert total_canonical == 1944
