import fitz
import re
from pathlib import Path

doc = fitz.open("data/generalization_notices/gen_01_tnpsc_assistant_jailor__men___women.pdf")
text = doc[2].get_text() # Page 3

# Test various patterns
pats = [
    # Original pattern 2:
    r"(?:Date\s*and\s*Time\s*of\s*Examination|Examination\s*Schedule)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){1,6}?\s*([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4})",
    
    # Relaxed header:
    r"(?:Date\s*(?:and\s*Time\s*)?of\s*(?:Written\s*|Computer\s*Based\s*Test\s*\(?CBT\)?\s*|Preliminary\s*|Descriptive\s*|Main\s*)?Examination|Examination\s*Schedule)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){1,8}?\s*([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4})",

    # Comprehensive multi-line header & multi-stage pattern:
    r"(?:Date\s*(?:and\s*Time\s*)?of\s*(?:[A-Za-z\(\)\/\s]{0,40})?Examination|Examination\s*Schedule)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,8}?\s*(?:Paper\s*[-–]\s*[I|1|A-Za-z0-9]+[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,3}?)?\s*([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4})"
]

for i, pat in enumerate(pats):
    m = re.search(pat, text, re.IGNORECASE)
    print(f"Pat {i}: {m.groups() if m else None}")
