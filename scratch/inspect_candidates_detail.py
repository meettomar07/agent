import sqlite3

conn = sqlite3.connect('data/testkart.db')
c = conn.cursor()

candidate_ids = [
    'not_57fca6f9a1c9', # UPSC Exam Time Table
    'not_d45c05a3f2ae', # UPSC Corrigendum
    'not_c2d5f50c09b8', # NTA Deputation
    'not_f00428943a2e', # UPPSC Blocked / Human Review Required
    'not_99f6cc7df5b8', # UPSC Result
    'not_2db460a18bee', # TNPSC Recruitment
    'not_9b1eef28c437', # NTA Cancellation
]

for nid in candidate_ids:
    print("=" * 60)
    cn = c.execute("SELECT id, authority_name, title, classification, status, recency_status, triage_flag, triage_notes FROM canonical_notices WHERE id = ?", (nid,)).fetchone()
    print("CANONICAL NOTICE:", cn)
    nvs = c.execute("SELECT id, version_number, document_type, length(raw_text), storage_path FROM notice_versions WHERE notice_id = ?", (nid,)).fetchall()
    print("VERSIONS:", nvs)
    for nv in nvs:
        facts = c.execute("SELECT fact_key, fact_value, verified_status, evidence_text, page_number FROM extracted_facts WHERE notice_version_id = ?", (nv[0],)).fetchall()
        print(f"FACTS for {nv[0]}: ({len(facts)} facts)")
        for f in facts:
            print("  ", f)
