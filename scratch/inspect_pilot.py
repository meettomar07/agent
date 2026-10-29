import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
conn = sqlite3.connect("data/testkart.db")
conn.row_factory = sqlite3.Row

articles = conn.execute("""
    SELECT ba.id as art_id, ba.canonical_notice_id, ba.template_type, ba.status, ba.current_version_id,
           cn.title as notice_title, cn.authority_name, cn.classification, cn.status as notice_status
    FROM blog_articles ba
    JOIN canonical_notices cn ON ba.canonical_notice_id = cn.id
""").fetchall()

for a in articles:
    print("=====================================================")
    print(f"Article: {a['art_id']} | Template: {a['template_type']} | Status: {a['status']}")
    print(f"Notice: {a['canonical_notice_id']} | Authority: {a['authority_name']} | Class: {a['classification']}")
    print(f"Title: {a['notice_title']}")
    
    # Versions
    vers = conn.execute("SELECT id, version_number, content_hash, created_at FROM article_versions WHERE article_id = ? ORDER BY version_number ASC", (a["art_id"],)).fetchall()
    print("Versions count:", len(vers))
    for v in vers:
        print(f"  v{v['version_number']}: {v['id']} (hash: {v['content_hash'][:12]}) created: {v['created_at']}")
    
    # Facts for this notice version
    nv = conn.execute("SELECT id FROM notice_versions WHERE notice_id = ? ORDER BY version_number DESC LIMIT 1", (a["canonical_notice_id"],)).fetchone()
    if nv:
        facts = conn.execute("SELECT fact_key, fact_value, evidence_text, page_number, verified_status FROM extracted_facts WHERE notice_version_id = ?", (nv["id"],)).fetchall()
        print(f"Facts ({len(facts)}):")
        for f in facts:
            ev = (f['evidence_text'] or '')[:60]
            print(f"  {f['fact_key']}: {f['fact_value']} [p.{f['page_number']}] ({f['verified_status']}) ev: {ev}")

    # Current version content snippet
    curr_v = conn.execute("SELECT content_markdown FROM article_versions WHERE id = ?", (a["current_version_id"],)).fetchone()
    if curr_v:
        md = curr_v["content_markdown"]
        lines = [line.strip() for line in md.split("\n") if line.strip()][:4]
        print("Markdown excerpt:")
        for l in lines:
            print("   ", l[:80])
