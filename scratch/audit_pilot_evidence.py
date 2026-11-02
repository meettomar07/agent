import sqlite3
import json

conn = sqlite3.connect('data/operational_pilot_30day.db')
conn.row_factory = sqlite3.Row

print('=== 1. SCAN RUNS ===')
runs = conn.execute('SELECT scan_type, status, count(*) as cnt FROM scan_runs GROUP BY scan_type, status').fetchall()
for r in runs:
    print(dict(r))
print('Total scan_runs count:', conn.execute('SELECT count(*) FROM scan_runs').fetchone()[0])

print('\n=== 2. SCAN RUNS BREAKDOWN ===')
all_runs = conn.execute('SELECT id, scan_type, status, started_at, sources_checked, notices_found, errors_count FROM scan_runs ORDER BY started_at').fetchall()
print(f'First run: {dict(all_runs[0])}')
print(f'Second run: {dict(all_runs[1])}')
print(f'Last run: {dict(all_runs[-1])}')

print('\n=== 3. SCAN SOURCE LOGS ===')
logs = conn.execute('SELECT status, count(*) as cnt FROM scan_source_logs GROUP BY status').fetchall()
for l in logs:
    print(dict(l))
print('Total scan_source_logs count:', conn.execute('SELECT count(*) FROM scan_source_logs').fetchone()[0])

print('\n=== 4. SOURCE LOGS PER SOURCE ===')
per_src = conn.execute('''
    SELECT os.code, count(*) as total_checks,
           sum(CASE WHEN ssl.status IN ('SUCCESS_NEW', 'SUCCESS_NO_NEW') THEN 1 ELSE 0 END) as succ,
           sum(CASE WHEN ssl.status = 'FAILED' THEN 1 ELSE 0 END) as failed
    FROM scan_source_logs ssl
    JOIN official_sources os ON os.id = ssl.source_id
    GROUP BY os.code
''').fetchall()
for s in per_src:
    print(dict(s))

print('\n=== 5. ALL FAILED SOURCE LOGS ===')
failed = conn.execute('SELECT id, scan_run_id, source_id, status, error_message, checked_at FROM scan_source_logs WHERE status = "FAILED"').fetchall()
for f in failed:
    print(dict(f))

print('\n=== 6. APPROVAL RECORDS ===')
apprs = conn.execute('''
    SELECT id, article_version_id, content_hash, reviewer_email, status, 
           decided_at, decision_notes, is_override, override_reason, unverified_fields_waived, client_ip, created_at
    FROM approval_records
''').fetchall()
print(f'Total approvals: {len(apprs)}')
for a in apprs:
    print(dict(a))

print('\n=== 7. AUDIT EVENTS FOR APPROVALS ===')
audit_apprs = conn.execute('''
    SELECT id, entity_type, entity_id, action, actor, payload_json, timestamp
    FROM audit_events
    WHERE entity_type IN ('approval_record', 'publishing_job')
''').fetchall()
for ae in audit_apprs:
    print(dict(ae))

print('\n=== 8. PUBLISHING JOBS ===')
pubs = conn.execute('SELECT id, article_version_id, approval_record_id, is_mock, status, published_url, executed_at FROM publishing_jobs').fetchall()
print(f'Total publishing jobs: {len(pubs)}')
for p in pubs:
    print(dict(p))

print('\n=== 9. DETAILED APPROVAL AUDIT ===')
rows = conn.execute('''
    SELECT ar.id as approval_id, ar.article_version_id, ar.reviewer_email, ar.status,
           ar.created_at, ar.decided_at, ar.decision_notes, ar.is_override, ar.client_ip,
           ba.id as article_id, ba.title as article_title, ba.slug,
           av.version_number, cn.id as notice_id, cn.title as notice_title, cn.authority_name
    FROM approval_records ar
    JOIN article_versions av ON av.id = ar.article_version_id
    JOIN blog_articles ba ON ba.id = av.article_id
    JOIN canonical_notices cn ON cn.id = ba.canonical_notice_id
    ORDER BY ar.decided_at ASC
''').fetchall()

for idx, r in enumerate(rows, start=1):
    print(f'Approval #{idx}:')
    print(f'  Approval ID:     {r["approval_id"]}')
    print(f'  Article:         {r["article_id"]} (v{r["version_number"]}) - {r["article_title"]}')
    print(f'  Notice:          {r["notice_id"]} - {r["notice_title"]} ({r["authority_name"]})')
    print(f'  Reviewer Email:  {r["reviewer_email"]}')
    print(f'  Decided At:      {r["decided_at"]}')
    print(f'  Decision Notes:  {r["decision_notes"]}')
    print(f'  Client IP:       {r["client_ip"]}')
    print(f'  Is Override:     {r["is_override"]}')
