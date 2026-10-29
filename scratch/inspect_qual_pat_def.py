with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('PATTERNS = [')
print(text[idx-50:idx+600])
