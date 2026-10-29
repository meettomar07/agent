with open('testkart_intelligence/extraction/verifier.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = 'and not any(tot in ev for tot in ("total", "grand total", "aggregate", "posts of", "post of", "posts:")):'
replacement = 'and not any(tot in ev for tot in ("total", "grand total", "aggregate")):'

if target in content:
    content = content.replace(target, replacement)
    with open('testkart_intelligence/extraction/verifier.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced successfully")
else:
    print("Target not found")
