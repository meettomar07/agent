import sqlite3
import re
import sys
sys.path.insert(0, ".")
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory

conn = sqlite3.connect("data/real_world_pilot_30day.db")
conn.row_factory = sqlite3.Row

# 1. Identify non-recruitment notices among non-QA_PASSED
non_passed = conn.execute("SELECT id, title, authority_name, normalized_url, status FROM canonical_notices WHERE status != 'QA_PASSED'").fetchall()

to_delete = []
to_keep = []

for n in non_passed:
    title = n["title"]
    url = n["normalized_url"]
    cat = NoticeClassifier.classify(title, url)
    if cat != NoticeCategory.RECRUITMENT_NOTIFICATION or "Ineligible List" in title or "Programme of Interview" in title or "Tamil Nadu Public Service Commission" in n["authority_name"]:
        to_delete.append(n["id"])
    else:
        to_keep.append(n["id"])

print(f"Non-recruitment to purge: {len(to_delete)}")
print(f"Genuine live recruitments to enrich: {len(to_keep)}")

if to_delete:
    with conn:
        conn.execute(f"DELETE FROM qa_results WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({','.join(['?']*len(to_delete))}))", to_delete)
        conn.execute(f"DELETE FROM approval_records WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({','.join(['?']*len(to_delete))}))", to_delete)
        conn.execute(f"DELETE FROM article_versions WHERE article_id IN (SELECT id FROM blog_articles WHERE canonical_notice_id IN ({','.join(['?']*len(to_delete))}))", to_delete)
        conn.execute(f"DELETE FROM blog_articles WHERE canonical_notice_id IN ({','.join(['?']*len(to_delete))})", to_delete)
        conn.execute(f"DELETE FROM extracted_facts WHERE notice_version_id IN (SELECT id FROM notice_versions WHERE notice_id IN ({','.join(['?']*len(to_delete))}))", to_delete)
        conn.execute(f"DELETE FROM notice_versions WHERE notice_id IN ({','.join(['?']*len(to_delete))})", to_delete)
        conn.execute(f"DELETE FROM canonical_notices WHERE id IN ({','.join(['?']*len(to_delete))})", to_delete)

rem_total = conn.execute("SELECT count(*) FROM canonical_notices").fetchone()[0]
qa_total = conn.execute("SELECT count(*) FROM canonical_notices WHERE status = 'QA_PASSED'").fetchone()[0]
print(f"Status: Total notices: {rem_total}, QA_PASSED: {qa_total}")
