import json

with open('scratch/harvested_generalization_candidates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total harvested: {len(data)}")
for d in data:
    print(f"{d['filename']}: {d['authority']} | {d['title']} | size={d['size_bytes']} | pages={d['page_count']} | readable={d['readable']}")
