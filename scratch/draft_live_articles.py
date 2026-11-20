import sqlite3
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent

conn = sqlite3.connect('data/real_world_pilot_30day.db')
conn.row_factory = sqlite3.Row

agent = WritingAgent()
qa = QualityAssuranceAgent()

notices_to_draft = [
    "not_c3f87ae192b2", # NTA Registration Extension
    "not_489c4fee4c59", # NTA Correction Window
    "not_fa52f955a289", # SSC Sub-Inspector Corrigendum
]

for nid in notices_to_draft:
    r = conn.execute("SELECT * FROM canonical_notices WHERE id = ?", (nid,)).fetchone()
    if not r:
        print(f"Notice {nid} not found")
        continue
    print(f"\nDrafting article for [{nid}] {r['title'][:50]}...")
    try:
        art_id, arv_id, _ = agent.draft_article(nid)
        passed, score, checks = qa.inspect_and_evaluate(arv_id)
        print(f"  -> Article: {art_id}, Version: {arv_id}, QA Passed: {passed}, Score: {score}")
    except Exception as exc:
        print(f"  -> Error: {exc}")

# Print total articles in DB
art_rows = conn.execute("SELECT id, title, status FROM blog_articles").fetchall()
print(f"\nTotal ready blog articles in DB: {len(art_rows)}")
for a in art_rows:
    print(f"  [{a['id']}] Status: {a['status']} | Title: {a['title'][:60]}")
