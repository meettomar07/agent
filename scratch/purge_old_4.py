import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
old_4 = ['not_1244be79c053', 'not_1f718df16cf2', 'not_38ba6b74ece9', 'not_e05506cb338f']

with conn:
    conn.execute(f"DELETE FROM qa_results WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({','.join(['?']*len(old_4))}))", old_4)
    conn.execute(f"DELETE FROM approval_records WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({','.join(['?']*len(old_4))}))", old_4)
    conn.execute(f"DELETE FROM article_versions WHERE article_id IN (SELECT id FROM blog_articles WHERE canonical_notice_id IN ({','.join(['?']*len(old_4))}))", old_4)
    conn.execute(f"DELETE FROM blog_articles WHERE canonical_notice_id IN ({','.join(['?']*len(old_4))})", old_4)
    conn.execute(f"DELETE FROM extracted_facts WHERE notice_version_id IN (SELECT id FROM notice_versions WHERE notice_id IN ({','.join(['?']*len(old_4))}))", old_4)
    conn.execute(f"DELETE FROM notice_versions WHERE notice_id IN ({','.join(['?']*len(old_4))})", old_4)
    conn.execute(f"DELETE FROM canonical_notices WHERE id IN ({','.join(['?']*len(old_4))})", old_4)

c = conn.cursor()
rem_notices = c.execute("SELECT count(*) FROM canonical_notices").fetchone()[0]
rem_articles = c.execute("SELECT count(*) FROM blog_articles").fetchone()[0]
qa_passed = c.execute("SELECT count(*) FROM blog_articles WHERE status = 'QA_PASSED'").fetchone()[0]
print(f"Remaining Notices: {rem_notices}, Articles: {rem_articles}, QA Passed: {qa_passed}")
