with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

replacement = '''        # Look for Educational Qualification / Eligibility
        qual_found = False
        if not is_result_or_key:'''

target = '''        # Look for Educational Qualification / Eligibility (skip text scan if table already extracted high-confidence qualification)
        qual_found = "eligibility" in extracted_keys
        if not is_result_or_key and not qual_found:'''

if target in text:
    text = text.replace(target, replacement)
    with open('testkart_intelligence/extraction/fact_extractor.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Reverted qual_found guard cleanly")
else:
    print("Target not found")
