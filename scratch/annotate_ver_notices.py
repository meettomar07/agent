import fitz
import sys
from pathlib import Path
import re

sys.stdout.reconfigure(encoding='utf-8')
ver_dir = Path("data/verification_notices")

for fname in ["ver_01_tnpsc_executive_officer_grade_i.pdf", "ver_02_tnpsc_assistant_professor_of_psychol.pdf", "ver_03_tnpsc_assistant_public_prosecutor_gr.pdf", "ver_04_tnpsc_statistician_in_medical_educat.pdf", "ver_11_tnpsc_assistant_geo_chemist.pdf"]:
    fpath = ver_dir / fname
    doc = fitz.open(fpath)
    print("=" * 80)
    print(fname)
    for pidx in range(min(5, len(doc))):
        text = doc[pidx].get_text()
        print(f"--- Page {pidx+1} ---")
        for line in text.splitlines():
            line_str = line.strip()
            if any(k in line_str.lower() for k in ("vacanc", "date", "fee", "age", "qualification", "examination")):
                print("  ", line_str)
