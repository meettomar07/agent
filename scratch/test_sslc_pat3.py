import re

text = 'The minimum general educational qualification means, a pass in the Secondary School \nLeaving Certificate (SSLC) Examination with eligibility for admission to college course of studies in'

m = re.search(r"minimum\s+general\s+educational\s+qualification\s+means,?\s*(?:a\s+pass\s+in\s+the\s+)?(Secondary\s+School\s+Leaving\s+Certificate\s+\(SSLC\))", text, re.IGNORECASE)
if m:
    print("Match:", m.group(1))
else:
    print("No match")
