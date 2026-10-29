import pymupdf

doc = pymupdf.open('data/development_notices/dev_13_tnpsc_special_competitive_exam.pdf')
for p in range(len(doc)):
    text = doc[p].get_text()
    if 'educational qualification' in text.lower() or 'sslc' in text.lower():
        print(f"=== Page {p+1} ===")
        for line in text.splitlines():
            if any(k in line.lower() for k in ('educational', 'qualification', 'sslc', 'diploma', 'minimum general')):
                print("  ", line)
