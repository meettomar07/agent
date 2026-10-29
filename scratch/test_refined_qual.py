import pymupdf
import re

doc = pymupdf.open('data/development_notices/dev_13_tnpsc_special_competitive_exam.pdf')

PATTERNS = [
    r"(?:^\s*|\n\s*)(?:4\.\d+\.?\s*)?(?:educational\s*and\s*technical\s*qualification|educational\s*qualification|minimum\s*qualification|essential\s*qualification|prescribed\s*qualification|eligibility\s*criteria)\s*[:\-]?\s*([^.\n]+?(?:Degree|Graduate|Graduation|10\+2|Matriculation|Diploma|Master|B\.E|B\.Tech|Bachelor|Secondary\s*School|SSLC)[^.\n]*)",
    r"(?:^\s*|\n\s*)(?:4\.\d+\.?\s*)?(?:educational\s*qualification|essential\s*qualification|minimum\s*qualification|eligibility\s*criteria)\s*[:\-]?\s*[\r\n]+(?:[^\n\r]*[\r\n]+){0,3}?[^\n\r]*?(Bachelor[']?s\s*Degree[^\.\n]*|Master[']?s\s*Degree[^\.\n]*|Diploma[^\.\n]*|Degree[^\.\n]*|Graduation[^\.\n]*|10\+2[^\.\n]*|Matriculation[^\.\n]*|SSLC[^\.\n]*|Secondary\s*School[^\.\n]*)",
    r"(?:Must\s*possess\s*Minimum\s*General\s*Educational\s*Qualification[^.\n]*)",
    r"(?:The\s*minimum\s*general\s*educational\s*qualification\s*means,?\s*([^.\n]+))",
]

for pno in range(len(doc)):
    text = doc[pno].get_text()
    for i, pat in enumerate(PATTERNS):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            print(f"Page {pno+1}, Pattern {i}:")
            print("  Full:", repr(m.group(0)[:120]))
            print("  Group 1:", repr(m.group(1) if len(m.groups()) >= 1 else None))
