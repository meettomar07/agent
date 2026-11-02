with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target1 = '        r"(?:Qualifications?|Eligibility)\\s*[:\\-–]\\s*([^\\n\\r]+)",'
replacement1 = '        r"(?:^|[\\r\\n])\\s*(?:Qualifications?|Eligibility)\\s*[:\\-–]\\s*([^\\n\\r]+)",'

assert target1 in content, f'target1 not found in content'
content = content.replace(target1, replacement1, 1)

target2 = 'if any(b in val_str.lower() for b in ["order of studies", "order of study", "pattern of study", "in the order of", "degree : institution : class", "higher than the"]):'
replacement2 = 'if any(b in val_str.lower() for b in ["order of studies", "order of study", "pattern of study", "in the order of", "degree : institution : class", "higher than the", "emergency commissioned", "short service commissioned", "for age relaxation", "age relaxation"]):'

assert target2 in content, f'target2 not found in content'
content = content.replace(target2, replacement2, 1)

with open('testkart_intelligence/extraction/fact_extractor.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Successfully patched fact_extractor.py')
