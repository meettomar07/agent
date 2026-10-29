import re
import pymupdf

doc = pymupdf.open('data/development_notices/dev_13_tnpsc_special_competitive_exam.pdf')
text = doc[2].get_text() # Page 3

PATTERNS = [
    r"(?:educational\s*and\s*technical\s*qualification|educational\s*qualification|minimum\s*qualification|essential\s*qualification|prescribed\s*qualification|eligibility\s*criteria)\s*[:\-]?\s*([^.\n]+?(?:Degree|Graduate|Graduation|10\+2|Matriculation|Diploma|Master|B\.E|B\.Tech|Bachelor|Secondary\s*School|SSLC)[^.\n]*)",
    r"(?:educational\s*qualification|essential\s*qualification|minimum\s*qualification|eligibility\s*criteria)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,3}?[^\n\r]*?(Bachelor[']?s\s*Degree[^\.\n]*|Master[']?s\s*Degree[^\.\n]*|Diploma[^\.\n]*|Degree[^\.\n]*|Graduation[^\.\n]*|10\+2[^\.\n]*|Matriculation[^\.\n]*)",
    r"(?:Must\s*possess\s*Minimum\s*General\s*Educational\s*Qualification[^.\n]*)",
    r"(?:posts\s*\(Educational\s*Qualifications-wise\s*viz\.\s*([^.\n\)]+)\))",
]

for pat_idx, pat in enumerate(PATTERNS):
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        print(f"Match on Page 3 with pattern {pat_idx}:")
        print("Raw match:", m.group(0))
        print("Groups:", m.groups())
