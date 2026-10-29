import fitz

doc = fitz.open("data/generalization_notices/gen_06_tnpsc_civil_judge_in_tamil_nadu_stat.pdf")
for pidx in [3, 4, 5]:
    text = doc[pidx].get_text()
    if "EDUCATIONAL" in text.upper():
        print(f"=== Page {pidx+1} ===")
        for line in text.splitlines():
            if any(k in line.lower() for k in ("educational", "degree", "qualification", "law", "practising")):
                print("  ", line)
