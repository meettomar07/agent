import re

with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

matches = [m.start() for m in re.finditer(r'key=[\"\']eligibility[\"\']', text)]
print("Matches found:", len(matches))
for m in matches:
    print(text[max(0, m-50):min(len(text), m+300)])
    print("="*60)
