import re

text = 'al educational qualification means, a pass in the Secondary School \nLeaving Certificate (SSLC) Examination with eligibility for admission to college course of studies in'

pat = r"The\s*minimum\s*general\s*educational\s*qualification\s*means,?\s*(?:a\s*pass\s*in\s*(?:the\s*)?)?([^\n\r]+?(?:Secondary\s*School\s*Leaving\s*Certificate\s*\(SSLC\)|SSLC)[^\n\r]*)"
m = re.search(pat, text, re.IGNORECASE)
if m:
    val_str = " ".join(m.group(1).split())
    print("Matched:", repr(val_str))
