with open('testkart_intelligence/extraction/verifier.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's inspect the exact lines around line 265
lines = text.splitlines()
for idx, line in enumerate(lines):
    if 'POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW' in line:
        for j in range(max(0, idx - 5), min(len(lines), idx + 5)):
            print(f"{j+1}: {lines[j]}")
