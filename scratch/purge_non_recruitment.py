import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
non_recruitment_nids = ['not_df52f5516b3d', 'not_839a568b699b', 'not_9e30ca3dcf2f', 'not_1e6b2fa37623']

with conn:
    conn.execute(f"DELETE FROM qa_results WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({','.join(['?']*len(non_recruitment_nids))}))", non_recruitment_nids)
    conn.execute(f"DELETE FROM approval_records WHERE article_version_id IN (SELECT av.id FROM article_versions av JOIN blog_articles ba ON av.article_id = ba.id WHERE ba.canonical_notice_id IN ({','.join(['?']*len(non_recruitment_nids))}))", non_recruitment_nids)
    conn.execute(f"DELETE FROM article_versions WHERE article_id IN (SELECT id FROM blog_articles WHERE canonical_notice_id IN ({','.join(['?']*len(non_recruitment_nids))}))", non_recruitment_nids)
    conn.execute(f"DELETE FROM blog_articles WHERE canonical_notice_id IN ({','.join(['?']*len(non_recruitment_nids))})", non_recruitment_nids)
    conn.execute(f"DELETE FROM extracted_facts WHERE notice_version_id IN (SELECT id FROM notice_versions WHERE notice_id IN ({','.join(['?']*len(non_recruitment_nids))}))", non_recruitment_nids)
    conn.execute(f"DELETE FROM notice_versions WHERE notice_id IN ({','.join(['?']*len(non_recruitment_nids))})", non_recruitment_nids)
    conn.execute(f"DELETE FROM canonical_notices WHERE id IN ({','.join(['?']*len(non_recruitment_nids))})", non_recruitment_nids)

c = conn.cursor()
arts = c.execute("SELECT status, count(*) FROM blog_articles GROUP BY status").fetchall()
print("Articles:", arts)
notices = c.execute("SELECT status, count(*) FROM canonical_notices GROUP BY status").fetchall()
print("Notices:", notices)
