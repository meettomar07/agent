import re
import sqlite3
from datetime import date, datetime
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

today = date(2026, 11, 18)

rows = conn.execute(
    """
    SELECT id, source_id, authority_name, state, title, normalized_url, classification,
           published_date, application_start_date, application_end_date, recency_status
    FROM canonical_notices
    """
).fetchall()

keep_ids = []
delete_ids = []
reasons = {}

for r in rows:
    nid = r["id"]
    title = r["title"] or ""
    url = r["normalized_url"] or ""
    auth = r["authority_name"] or ""

    # 0. Reject empty/JSON titles and known expired CGEPT notice
    if not title.strip() or len(title.strip()) < 10 or title.strip().startswith("{") or "coast guard" in title.lower():
        delete_ids.append(nid)
        reasons["junk_or_expired"] = reasons.get("junk_or_expired", 0) + 1
        continue

    # 1. Re-classify strictly for Recruitment-Only
    cat = NoticeClassifier.classify(title, url)
    if cat != NoticeCategory.RECRUITMENT_NOTIFICATION or "national testing agency" in auth.lower():
        delete_ids.append(nid)
        reasons["non_recruitment"] = reasons.get("non_recruitment", 0) + 1
        continue

    # 2. Remove expired by application_end_date
    end_str = r["application_end_date"]
    if end_str and re.match(r"^\d{4}-\d{2}-\d{2}$", end_str):
        try:
            if datetime.strptime(end_str, "%Y-%m-%d").date() < today:
                delete_ids.append(nid)
                reasons["expired_end_date"] = reasons.get("expired_end_date", 0) + 1
                continue
        except Exception:
            pass

    # 3. Remove historical 2010-2025 archive notices (unless explicitly 2026/2027)
    has_old_year = bool(re.search(r"\b(201[0-9]|202[0-5])\b", title) or re.search(r"(?:^|[/_\-])(201[0-9]|202[0-5])(?:[/_\-\.]|$)", url))
    has_curr_year = ("2026" in title or "2027" in title or "2026" in url or "2027" in url)
    if has_old_year and not has_curr_year:
        delete_ids.append(nid)
        reasons["historical_archive"] = reasons.get("historical_archive", 0) + 1
        continue

    if r["recency_status"] in ("HISTORICAL", "EXPIRED"):
        delete_ids.append(nid)
        reasons["status_expired"] = reasons.get("status_expired", 0) + 1
        continue

    # 4. Update classification to RECRUITMENT_NOTIFICATION and keep
    keep_ids.append(nid)

print(f"Total evaluated: {len(rows)}")
print(f"Removing: {len(delete_ids)} -> Breakdown: {reasons}")
print(f"Keeping (Live Pan-India Recruitment Only): {len(keep_ids)}")

if delete_ids:
    with conn:
        ph = ",".join(["?"] * len(delete_ids))
        conn.execute(
            f"DELETE FROM qa_results WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({ph}))",
            delete_ids,
        )
        conn.execute(
            f"DELETE FROM approval_records WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({ph}))",
            delete_ids,
        )
        conn.execute(
            f"DELETE FROM article_versions WHERE article_id IN (SELECT id FROM blog_articles WHERE canonical_notice_id IN ({ph}))",
            delete_ids,
        )
        conn.execute(f"DELETE FROM blog_articles WHERE canonical_notice_id IN ({ph})", delete_ids)
        conn.execute(
            f"DELETE FROM extracted_facts WHERE notice_version_id IN (SELECT id FROM notice_versions WHERE notice_id IN ({ph}))",
            delete_ids,
        )
        conn.execute(f"DELETE FROM notice_versions WHERE notice_id IN ({ph})", delete_ids)
        conn.execute(f"DELETE FROM canonical_notices WHERE id IN ({ph})", delete_ids)

# Print remaining breakdown by state and authority
print("\n=== LIVE PAN-INDIA RECRUITMENT NOTICES BY STATE / AUTHORITY ===")
summary = conn.execute(
    """
    SELECT state, authority_name, count(*) as cnt
    FROM canonical_notices
    GROUP BY state, authority_name
    ORDER BY cnt DESC
    """
).fetchall()
for s in summary:
    print(f"  - {s['state']:<16} | {s['authority_name']:<45} | {s['cnt']} live recruitment(s)")

print("\n=== TOP 25 LIVE PAN-INDIA RECRUITMENTS ===")
top = conn.execute(
    """
    SELECT id, state, authority_name, title, normalized_url
    FROM canonical_notices
    ORDER BY first_discovered_at DESC
    LIMIT 25
    """
).fetchall()
for t in top:
    print(f"  [{t['id']}] ({t['state']} - {t['authority_name'][:20]}) {t['title'][:65]}")
