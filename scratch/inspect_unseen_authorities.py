import json
from collections import Counter

with open("scratch/unseen_real_docs.json", "r", encoding="utf-8") as f:
    docs = json.load(f)

print(f"Total unseen real docs: {len(docs)}")

# Classify authority and notice title / type
classified = []
for d in docs:
    txt = d["text"].lower()
    auth = "UNKNOWN"
    if "union public service commission" in txt or "upsc" in txt or "dholpur house" in txt:
        auth = "UPSC"
    elif "staff selection commission" in txt or "ssc" in txt:
        auth = "SSC"
    elif "national testing agency" in txt or "nta" in txt:
        auth = "NTA"
    elif "tamil nadu public service commission" in txt or "tnpsc" in txt:
        auth = "TNPSC"
    elif "uttar pradesh public service commission" in txt or "uppsc" in txt:
        auth = "UPPSC"
    
    classified.append((auth, d))

counts = Counter([c[0] for c in classified])
print("Authority distribution:", counts)

# Sample a few from each
by_auth = {}
for auth, d in classified:
    by_auth.setdefault(auth, []).append(d)

for auth, items in by_auth.items():
    print(f"\n=== Authority: {auth} ({len(items)} items) ===")
    for it in items[:3]:
        print(f"  File: {it['filename']} | Pages: {it['page_count']} | Size: {it['size_bytes']}")
        print(f"  Snippet: {it['text'][:200]}\n")
