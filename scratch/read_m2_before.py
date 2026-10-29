import re

with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

matches = [m.start() for m in re.finditer(r'key=[\"\']eligibility[\"\']', text)]
m2 = matches[1]
print(text[m2-1500:m2])
