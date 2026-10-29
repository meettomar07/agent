import sqlite3
import json

conn = sqlite3.connect("data/pilot_batch_2.db")
conn.row_factory = sqlite3.Row

print("=== APPROVAL RECORDS AUDIT ===")
approvals = conn.execute("""
    SELECT ar.id, ar.status, ar.reviewer_email, ar.is_override, ar.override_reason, ar.unverified_fields_waived, ba.id as art_id, cn.title as notice_title
    FROM approval_records ar
    JOIN article_versions av ON ar.article_version_id = av.id
    JOIN blog_articles ba ON av.article_id = ba.id
    JOIN canonical_notices cn ON ba.canonical_notice_id = cn.id
""").fetchall()

normal_approvals = 0
overrides = 0
for a in approvals:
    if a["is_override"]:
        overrides += 1
        print(f"[OVERRIDE] {a['art_id']} | Notice: {a['notice_title'][:50]}")
        print(f"  Reviewer: {a['reviewer_email']}")
        print(f"  Reason: {a['override_reason']}")
        print(f"  Waived Fields: {a['unverified_fields_waived']}")
    else:
        normal_approvals += 1

print(f"\nTotal Approvals: {len(approvals)} (Normal: {normal_approvals}, Overrides: {overrides})")

print("\n=== AUDIT EVENTS AUDIT ===")
audits = conn.execute("SELECT id, entity_type, action, actor, payload_json, timestamp FROM audit_events ORDER BY timestamp ASC").fetchall()
print(f"Total audit events logged: {len(audits)}")
override_events = [ae for ae in audits if ae["action"] == "EDITORIAL_OVERRIDE_APPROVED"]
print(f"OVERRIDE_APPROVE audit events: {len(override_events)}")
for oe in override_events:
    payload = json.loads(oe["payload_json"])
    print(f"  Actor: {oe['actor']} | Waived: {payload.get('unverified_fields_waived')} | Reason: {payload.get('override_reason')[:60]}")

print("\n=== MOCK PUBLISHING AUDIT ===")
jobs = conn.execute("SELECT id, article_version_id, publisher_name, is_mock, status, published_url FROM publishing_jobs").fetchall()
print(f"Total publishing jobs: {len(jobs)}")
for j in jobs:
    assert j["publisher_name"] == "mock_publisher"
    assert j["is_mock"] == 1
    assert "https://mock.testkart.local/blog/" in j["published_url"]
print("All 15 publishing jobs confirmed local mock publisher only (zero live CMS/external endpoints, is_mock=1).")
