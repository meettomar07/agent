with open("testkart_intelligence/extraction/verifier.py", encoding="utf-8") as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if "eligibility" in l.lower() or "gate_7" in l.lower() or "truncated" in l.lower():
        print(f"Line {i+1}: {l.strip()}")
