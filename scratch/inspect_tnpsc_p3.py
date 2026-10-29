import pymupdf

doc = pymupdf.open("data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf")
for pno in [2, 3, 4]:
    print(f"=== Page {pno+1} text snippet ===")
    lines = doc[pno].get_text().split("\n")
    for l in lines[:30]:
        if l.strip():
            print(" ", l.strip().encode("ascii", errors="replace").decode("ascii"))
doc.close()
