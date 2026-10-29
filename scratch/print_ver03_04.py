import fitz
import sys

sys.stdout.reconfigure(encoding='utf-8')

for fname in ["ver_03_tnpsc_assistant_public_prosecutor_gr.pdf", "ver_04_tnpsc_statistician_in_medical_educat.pdf"]:
    doc = fitz.open(f"data/verification_notices/{fname}")
    print("=" * 80)
    print(fname)
    for pidx in range(min(4, len(doc))):
        text = doc[pidx].get_text()
        print(f"--- Page {pidx+1} ---")
        for line in text.splitlines():
            line_str = line.strip()
            if any(k in line_str.lower() for k in ("vacanc", "date of written", "date of notification", "last date", "advt", "notification no", "fee", "maximum age", "others")):
                print("  ", line_str)
