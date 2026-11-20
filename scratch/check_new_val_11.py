import fitz

doc = fitz.open("data/new_validation_notices/new_val_11_tnpsc_hostel_superintendent_cum_phys.pdf")
print("Total pages:", len(doc))
for i in range(min(5, len(doc))):
    txt = doc[i].get_text()
    for l in txt.split("\n"):
        if "2024" in l or "28.01" in l or "21.01" in l:
            print(f"P{i+1}: {l.strip()}")
