with open('testkart_intelligence/extraction/verifier.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = 'if re.search(r"distribution of vacancies|breakup of vacancies", full_text, re.IGNORECASE):'
replacement = 'if re.search(r"distribution of vacancies|breakup of vacancies|tabular breakdown|breakdown", full_text, re.IGNORECASE):'

if target in content:
    content = content.replace(target, replacement)
    with open('testkart_intelligence/extraction/verifier.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced target in verifier.py successfully")
else:
    print("Target string not found!")
