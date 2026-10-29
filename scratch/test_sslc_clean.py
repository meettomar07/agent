import pymupdf
import re

doc = pymupdf.open('data/development_notices/dev_13_tnpsc_special_competitive_exam.pdf')
text = doc[3].get_text() # Page 4

pat = r"The\s*minimum\s*general\s*educational\s*qualification\s*means,?\s*([^.\n]+(?:\([^\)]+\))?[^.\n]*)"
m = re.search(pat, text, re.IGNORECASE)
if m:
    val_str = " ".join(m.group(1).split())
    val_str = re.sub(r"^(?:means,?\s*|a\s+pass\s+in\s+(?:the\s+)?)+", "", val_str, flags=re.I).strip()
    print("Extracted val_str:", repr(val_str))
