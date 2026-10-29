import pymupdf

doc = pymupdf.open('data/development_notices/dev_09_tnpsc_cts_non_interview_posts.pdf')
for p in range(10, 14):
    print(f"=== Page {p+1} ===")
    print(doc[p].get_text()[:1000])
