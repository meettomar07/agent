import sqlite3
import re
from testkart_intelligence.classification.classifier import NoticeClassifier, NoticeCategory

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row

conn.execute("""
CREATE TABLE canonical_notices (
    id TEXT PRIMARY KEY,
    source_id TEXT,
    title TEXT,
    notice_number TEXT,
    classification TEXT,
    first_discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Register parent recruitment notices in DB
parents = [
    ("not_parent_ssc_gd", "src_ssc", "Notice of Constable (GD) in Central Armed Police Forces Examination, 2026", "Notice No. 3/1/2026-P&P-I", "RECRUITMENT_NOTIFICATION"),
    ("not_parent_upsc_law", "src_upsc", "Advertisement No. 12/2026 for Recruitment to 18 Posts of Assistant Director (Law)", "Advt. No. 12/2026", "RECRUITMENT_NOTIFICATION"),
    ("not_parent_uppsc_acf", "src_uppsc", "Combined State Upper Subordinate Services / ACF / RFO Examination 2026", "Advt. No. A-2/E-1/2026", "RECRUITMENT_NOTIFICATION"),
    ("not_parent_tnpsc_grp1", "src_tnpsc", "Combined Civil Services Examination I (Group I Services) Notification No. 12/2026", "Notification No. 12/2026", "RECRUITMENT_NOTIFICATION"),
]

for p in parents:
    conn.execute("INSERT INTO canonical_notices VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", p)
conn.commit()

test_cases = [
    # 1. Corrigendum with matching notice number
    ("child_ssc", "src_ssc", "Corrigendum to Constable (GD) in Central Armed Police Forces Examination, 2026", "F.No. 3/1/2026-P&P-I", NoticeCategory.CORRIGENDUM, "not_parent_ssc_gd"),
    # 2. Addendum with matching notice number
    ("child_upsc", "src_upsc", "Addendum to Advertisement No. 12/2026 for Recruitment to the Post of Assistant Director (Law)", "Advt. No. 12/2026", NoticeCategory.RECRUITMENT_ADDENDUM, "not_parent_upsc_law"),
    # 3. Corrigendum with matching notice number
    ("child_uppsc", "src_uppsc", "Corrigendum to Assistant Conservator of Forest / Range Forest Officer Examination 2026", "Advt. No. A-2/E-1/2026", NoticeCategory.CORRIGENDUM, "not_parent_uppsc_acf"),
    # 4. Standalone Admit Card with overlapping title ("Combined Civil Services Examination I") but own press release number
    ("admit_tnpsc", "src_tnpsc", "Press Release: Release of Hall Ticket / Admit Card for Combined Civil Services Examination I", "Press Release No. 62/2026", NoticeCategory.ADMIT_CARD_RELEASE, None),
]

for nid, sid, title, nn, cat, expected_parent in test_cases:
    pid, rel_type, conf, notes = NoticeClassifier.link_to_parent_notice(
        notice_id=nid,
        source_id=sid,
        title=title,
        notice_number=nn,
        category=cat,
        conn=conn
    )
    print(f"\nNotice: '{title}' [{cat.value}]")
    print(f"  Result: parent_id={pid}, conf={conf}, notes={notes}")
    assert pid == expected_parent, f"Expected {expected_parent}, got {pid}"
    print(f"  PASS: Expected {expected_parent} == Actual {pid}")

print("\nALL PARENT LINKING TESTS PASSED PERFECTLY!")
