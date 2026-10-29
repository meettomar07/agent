import pymupdf
from pathlib import Path

doc = pymupdf.open("data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf")
print("=== Page 1 text ===")
print(doc[0].get_text()[:2500])

print("\n=== Page 2 text ===")
print(doc[1].get_text()[:2500])
doc.close()
