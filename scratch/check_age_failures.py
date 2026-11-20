from pathlib import Path
import fitz

val_dir = Path("data/new_validation_notices")
age_fails = [
    ("new_val_01_tnpsc_combined_civil_services_examin.pdf", "18 to 35 years"),
    ("new_val_02_tnpsc_assistant_public_prosecutor__g.pdf", "34 years"),
    ("new_val_03_tnpsc_combined_technical_services_ex.pdf", "32 years"),
    ("new_val_04_tnpsc_combined_technical_services_ex.pdf", "32 years"),
    ("new_val_05_tnpsc_combined_civil_services_examin.pdf", "32 years"),
    ("new_val_06_tnpsc_combined_civil_services_examin.pdf", "21 to 34 years"),
    ("new_val_07_tnpsc_rashtriya_indian_military_coll.pdf", "11.5 to 13 years"),
    ("new_val_10_tnpsc_combined_accounts_services_exa.pdf", "18 to 32 years"),
    ("new_val_11_tnpsc_hostel_superintendent_cum_phys.pdf", "18 to 37 years"),
    ("new_val_12_tnpsc_combined_engineering_services.pdf", "18 to 32 years"),
    ("new_val_13_tnpsc_executive_officer__grade_i__gr.pdf", "30 to 37 years"),
    ("new_val_14_tnpsc_mass_interviewer_in_public_hea.pdf", "18 to 32 years"),
    ("new_val_15_tnpsc_junior_analyst_in_the_drugs_te.pdf", "18 to 32 years"),
    ("new_val_46_ssc_notification_for_recruitment_o.pdf", "18 to 22 years"),
]

for fname, exp in age_fails:
    fpath = val_dir / fname
    doc = fitz.open(fpath)
    print(f"\n{'='*20} {fname} (Expected: {exp}) {'='*20}")
    found = False
    for i, p in enumerate(doc):
        txt = p.get_text()
        if "AGE LIMIT" in txt.upper() or "AGE CRITERIA" in txt.upper() or "AGE (AS ON" in txt.upper() or "AGE:" in txt.upper():
            print(f"--- Page {i+1} ---")
            lines = [l.strip() for l in txt.split("\n") if l.strip()]
            for j, line in enumerate(lines):
                if any(k in line.upper() for k in ["AGE LIMIT", "AGE (AS ON", "MINIMUM AGE", "MAXIMUM AGE"]):
                    snippet = " // ".join(lines[j:min(len(lines), j+15)])
                    print(f"  Snippet: {snippet[:200]}")
                    found = True
                    break
            if found:
                break
