from pathlib import Path
import fitz

val_dir = Path("data/new_validation_notices")
cases = [
    ("new_val_21_nta_inviting_online_application_fo.pdf", "07.12.2026"),
    ("new_val_26_nta_ugc_net_exam_june_2026___3__su.pdf", "04.09.2026"),
    ("new_val_29_nta_announcement_of_date_s__for_st.pdf", "07.12.2026"),
    ("new_val_34_upsc_examination_time_table__combin.html", "07.02.2027"),
    ("new_val_47_ssc_important_notice___schedule_of.pdf", "18.11.2026"),
    ("new_val_50_ssc_important_notice__grade__c__st.pdf", "09.05.2025"),
]

for fname, exp in cases:
    fpath = val_dir / fname
    print(f"\n{'='*20} {fname} (Expected: {exp}) {'='*20}")
    if fname.endswith(".html"):
        txt = fpath.read_text(encoding="utf-8", errors="replace")
    else:
        doc = fitz.open(fpath)
        txt = "\n---PAGE---\n".join(p.get_text() for p in doc)
    
    print(f"File length: {len(txt)} chars")
    # Search for expected date or components
    if exp in txt:
        print(f"EXACT '{exp}' FOUND IN TEXT!")
        for line in txt.split("\n"):
            if exp in line:
                print(f"  Line: {line.strip()}")
    else:
        print(f"'{exp}' NOT found directly.")
        d, m, y = exp.split(".") if "." in exp else exp.split("/")
        for line in txt.split("\n"):
            if y in line and any(w in line.lower() for w in ["exam", "test", "held", "date", "schedule"]):
                print(f"  Candidate: {line.strip()[:100]}")
