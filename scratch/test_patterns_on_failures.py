import fitz
import re
from testkart_intelligence.extraction.fact_extractor import FactExtractor

doc = fitz.open("data/new_validation_notices/new_val_01_tnpsc_combined_civil_services_examin.pdf")
p3_text = doc[2].get_text()

print("--- Testing QUALIFICATION_PATTERNS on new_val_01 Page 3 ---")
for i, pat in enumerate(FactExtractor.QUALIFICATION_PATTERNS):
    m = re.search(pat, p3_text, re.IGNORECASE)
    print(f"Pattern {i}: {'MATCH' if m else 'NO MATCH'}")
    if m:
        print(f"  Matched: {m.group(0)[:100]}")
        if m.groups():
            print(f"  Group 1: {m.group(1)[:100]}")
