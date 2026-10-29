import pymupdf

doc = pymupdf.open('data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf')
print("Page 17 text:")
print(doc[16].get_text()[:1500])
