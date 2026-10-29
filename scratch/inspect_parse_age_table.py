with open('testkart_intelligence/extraction/table_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('def _parse_age_table')
print(text[idx:idx+1500])
