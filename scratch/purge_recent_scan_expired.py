import sqlite3
import re

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

# Find all notices that are historical/expired from past years
all_notices = conn.execute("SELECT id, title, authority_name, status, normalized_url FROM canonical_notices").fetchall()

expired_ids = []
for n in all_notices:
    title = n["title"]
    url = n["normalized_url"]
    
    # Archive url
    if re.search(r'/(archive|archived|previous|old_advertisements?|old_notices?)/', url, re.I):
        expired_ids.append((n["id"], n["authority_name"], title[:60]))
        continue
        
    # Past years prior to current cycle (1990 - 2024) without 2026/2027
    past_years = [int(y) for y in re.findall(r'\b(19\d\d|200\d|201\d|202[0-4])\b', title)]
    has_live_year = bool(re.search(r'\b(2026|2027|2028)\b', title))
    
    if past_years and not has_live_year:
        expired_ids.append((n["id"], n["authority_name"], title[:60]))

print(f"Total notices to purge: {len(expired_ids)}")
for eid, auth, t in expired_ids[:10]:
    print(f" - [{auth}] {t}")

ids_to_del = [e[0] for e in expired_ids]
if ids_to_del:
    with conn:
        conn.execute(f"DELETE FROM qa_results WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({','.join(['?']*len(ids_to_del))}))", ids_to_del)
        conn.execute(f"DELETE FROM approval_records WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({','.join(['?']*len(ids_to_del))}))", ids_to_del)
        conn.execute(f"DELETE FROM article_versions WHERE article_id IN (SELECT id FROM blog_articles WHERE canonical_notice_id IN ({','.join(['?']*len(ids_to_del))}))", ids_to_del)
        conn.execute(f"DELETE FROM blog_articles WHERE canonical_notice_id IN ({','.join(['?']*len(ids_to_del))})", ids_to_del)
        conn.execute(f"DELETE FROM extracted_facts WHERE notice_version_id IN (SELECT id FROM notice_versions WHERE notice_id IN ({','.join(['?']*len(ids_to_del))}))", ids_to_del)
        conn.execute(f"DELETE FROM notice_versions WHERE notice_id IN ({','.join(['?']*len(ids_to_del))})", ids_to_del)
        conn.execute(f"DELETE FROM canonical_notices WHERE id IN ({','.join(['?']*len(ids_to_del))})", ids_to_del)

rem = conn.execute("SELECT count(*) FROM canonical_notices").fetchone()[0]
rem_arts = conn.execute("SELECT count(*) FROM blog_articles WHERE status = 'QA_PASSED'").fetchone()[0]
print(f"Purge complete! Remaining notices: {rem}, QA_PASSED articles: {rem_arts}")
