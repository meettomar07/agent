from pathlib import Path
import re

p = Path("data/development_notices/dev_11_upsc_vice_principal_gnctd_notice.html")
text = p.read_text(encoding="utf-8", errors="replace")
print("Length:", len(text))
for line in text.splitlines():
    if any(k in line.lower() for k in ["vacancy", "post", "candidate", "advertisement", "item"]):
        print(line[:120])
