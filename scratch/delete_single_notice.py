import sqlite3

conn = sqlite3.connect("data/real_world_pilot_30day.db")
with conn:
    conn.execute("DELETE FROM canonical_notices WHERE id = 'not_0fb4f55808ae'")

c = conn.cursor()
rem_notices = c.execute("SELECT count(*) FROM canonical_notices").fetchone()[0]
rem_articles = c.execute("SELECT count(*) FROM blog_articles").fetchone()[0]
qa_passed = c.execute("SELECT count(*) FROM blog_articles WHERE status = 'QA_PASSED'").fetchone()[0]
print(f"Remaining Notices: {rem_notices}, Articles: {rem_articles}, QA Passed: {qa_passed}")
