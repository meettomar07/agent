import os
for root, dirs, files in os.walk("testkart_intelligence"):
    for file in files:
        if file.endswith(".py"):
            p = os.path.join(root, file)
            with open(p, encoding="utf-8") as f:
                content = f.read()
                if "Single Post Table Row" in content or "single post" in content.lower():
                    for i, l in enumerate(content.split("\n")):
                        if "single post" in l.lower():
                            print(f"{p}:{i+1}: {l.strip()}")
