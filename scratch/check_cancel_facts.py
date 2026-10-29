import sqlite3

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

facts = c.execute("SELECT fact_key, fact_value, verified_status, evidence_text, page_number FROM extracted_facts WHERE notice_version_id = 'ver_1bdec31e7377'").fetchall()
print(f"Facts for ver_1bdec31e7377 ({len(facts)}):")
for f in facts:
    print(" ", f)

cn = c.execute("SELECT id, status, classification, triage_flag, triage_notes FROM canonical_notices WHERE id = 'not_9b1eef28c437'").fetchone()
print("Notice status:", cn)
