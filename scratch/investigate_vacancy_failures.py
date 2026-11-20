from pathlib import Path
import fitz

val_dir = Path("data/new_validation_notices")
vac_cases = [
    ("new_val_03_tnpsc_combined_technical_services_ex.pdf", "22", "105"),
    ("new_val_04_tnpsc_combined_technical_services_ex.pdf", "118", "5"),
    ("new_val_08_tnpsc_combined_civil_services_examin.pdf", "6244", "108"),
    ("new_val_09_tnpsc_assistant_agricultural_officer.pdf", "263", "3"),
    ("new_val_10_tnpsc_combined_accounts_services_exa.pdf", "52", "04"),
    ("new_val_12_tnpsc_combined_engineering_services.pdf", "369", "45"),
    ("new_val_16_tnpsc_research_assistant_in_the_inst.pdf", "06", "37"),
    ("new_val_51_ssc_tentative_vacancy_of_combined.pdf", "17727", "10731"),
]

for fname, exp, got in vac_cases:
    fpath = val_dir / fname
    doc = fitz.open(fpath)
    print(f"\n{'='*20} {fname} (Expected: {exp}, Got: {got}) {'='*20}")
    # Search for expected and got in the first 5 pages
    for i in range(min(5, len(doc))):
        txt = doc[i].get_text()
        has_exp = exp in txt
        has_got = got in txt
        if has_exp or has_got or "vacanc" in txt.lower():
            lines = [l.strip() for l in txt.split("\n") if l.strip()]
            for j, l in enumerate(lines):
                if exp in l or got in l or "total" in l.lower() or "vacanc" in l.lower():
                    snippet = " // ".join(lines[max(0, j-2):min(len(lines), j+3)])
                    print(f"  [P{i+1}]: {snippet[:140]}")
