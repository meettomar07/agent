from testkart_intelligence.extraction.fact_extractor import FactExtractor
import re

text = """After the last date for submission of online application, the Application Correction Window will be open from 19.11.2024 to 21.11.2024"""

for i, pat in enumerate(FactExtractor.END_DATE_PATTERNS):
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        print(f"Matched END_DATE_PATTERNS[{i}]: {m.group(0)} -> group 1: {m.group(1)}")
