import re

with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('qual_found = False')
print(text[idx:idx+1200])
