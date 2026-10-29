import re

text = 'al educational qualification means, a pass in the Secondary School \nLeaving Certificate (SSLC) Examination with eligibility for admission to college course of studies in'

# Notice 'Secondary School \nLeaving Certificate' has a newline!
pat = r"(?:The\s*)?minimum\s*general\s*educational\s*qualification\s*means,?\s*(?:a\s*pass\s*in\s*(?:the\s*)?)?((?:Secondary\s*School\s*Leaving\s*Certificate\s*\(SSLC\)|SSLC)[^.\n]*)"
# If we normalize whitespace first or use \s+
pat2 = r"(?:The\s*)?minimum\s*general\s*educational\s*qualification\s*means,?\s*(?:a\s*pass\s*in\s*(?:the\s*)?)?([^\n\r.]+?\s*\(SSLC\)[^.\n]*)"
m = re.search(r"(?:The\s*)?minimum\s*general\s*educational\s*qualification\s*means,?\s*(?:a\s*pass\s*in\s*(?:the\s*)?)?(Secondary\s+School\s+Leaving\s+Certificate\s+\(SSLC\))", " ".join(text.split()), re.IGNORECASE)
if m:
    print("Matched with space collapse:", repr(m.group(1)))
