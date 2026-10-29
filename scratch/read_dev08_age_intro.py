import pymupdf

doc = pymupdf.open('data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf')
for p in range(14, 18):
    text = doc[p].get_text()
    if 'age limit' in text.lower() or '4.1' in text:
        print(f"=== Page {p+1} ===")
        print(text[:1200])
