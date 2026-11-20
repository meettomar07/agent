with open("testkart_intelligence/extraction/fact_extractor.py", encoding="utf-8") as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if '"eligibility"' in l and ('key=' in l or 'key =' in l or 'key == ' in l):
        print(f"Line {i+1}: {l.strip()}")
