import sqlite3

conn = sqlite3.connect("data/testkart.db")
c = conn.cursor()

print("=== ALL SCAN RUNS IN testkart.db ===")
runs = c.execute("SELECT id, scan_type, status, started_at, completed_at, sources_checked, notices_found, errors_count, error_summary FROM scan_runs ORDER BY started_at ASC").fetchall()
for r in runs:
    print(r)

print("\n=== SOURCE LOG COUNTS BY STATUS ===")
logs = c.execute("SELECT status, count(*) FROM scan_source_logs GROUP BY status").fetchall()
for l in logs:
    print(l)
