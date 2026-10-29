with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(100, 120):
    if i < len(lines):
        print(f"{i+1}: {repr(lines[i])}")
