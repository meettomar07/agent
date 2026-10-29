import json

with open("scratch/candidates_found.json", "r", encoding="utf-8") as f:
    candidates = json.load(f)

print(f"Total candidates: {len(candidates)}")
for i, c in enumerate(candidates[:10]):
    print(f"[{i+1}] {c['file']} ({c['pages']} pages, {c['size_bytes']} bytes)")
    print("   Snippet:", c["snippet"][:150])
