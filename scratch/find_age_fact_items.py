with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('age_limit')
while idx != -1:
    if 'ExtractedFactItem' in text[idx-100:idx+200]:
        print(f"Match around {idx}:")
        print(text[max(0, idx-100):min(len(text), idx+200)])
        print("="*60)
    idx = text.find('age_limit', idx + 1)
