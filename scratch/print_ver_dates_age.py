import fitz
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ver_dir = Path("data/verification_notices")

for fname in ["ver_01_tnpsc_executive_officer_grade_i.pdf", "ver_02_tnpsc_assistant_professor_of_psychol.pdf", "ver_03_tnpsc_assistant_public_prosecutor_gr.pdf", "ver_04_tnpsc_statistician_in_medical_educat.pdf", "ver_11_tnpsc_assistant_geo_chemist.pdf"]:
    fpath = ver_dir / fname
    doc = fitz.open(fpath)
    print("=" * 80)
    print(f"NOTICE: {fname}")
    for pidx in range(min(3, len(doc))):
        text = doc[pidx].get_text()
        lines = text.splitlines()
        for i, l in enumerate(lines):
            if any(k in l.upper() for k in ("IMPORTANT DATES", "AGE (AS ON", "AGE LIMIT", "DETAILS OF VACANCIES")):
                print(f"--- Page {pidx+1} Around: {l} ---")
                for sub in lines[i:min(len(lines), i+25)]:
                    print("  ", sub)
