import fitz

for fname in ["gen_01_tnpsc_assistant_jailor__men___women.pdf", "gen_06_tnpsc_civil_judge_in_tamil_nadu_stat.pdf"]:
    doc = fitz.open(f"data/generalization_notices/{fname}")
    print("=" * 80)
    print(fname)
    for pidx in range(len(doc)):
        text = doc[pidx].get_text()
        if "5. QUALIFICATIONS" in text.upper() or "EDUCATIONAL QUALIFICATION" in text.upper():
            lines = text.split("\n")
            for lno, l in enumerate(lines):
                if "EDUCATIONAL QUALIFICATION" in l.upper() or "(B) EDUCATIONAL" in l.upper():
                    print(f"Page {pidx+1}, Line {lno}:")
                    for ctx in lines[lno:lno+15]:
                        print("  ", ctx)
