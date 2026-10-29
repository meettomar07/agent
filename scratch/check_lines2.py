import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(100, 125):
    if i < len(lines):
        print(f"{i+1}: {repr(lines[i])}")
