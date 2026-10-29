import json
from pathlib import Path

data_dir = Path("data/generalization_notices")
with open("scratch/harvested_generalization_candidates.json", "r", encoding="utf-8") as f:
    items = json.load(f)

new_items = []
for idx, item in enumerate(items, 1):
    old_fname = item["filename"]
    # keep the prefix and slug
    # old_fname format: gen_XX_prefix_slug.ext
    parts = old_fname.split("_", 2)
    new_fname = f"gen_{idx:02d}_{parts[2]}"
    old_path = data_dir / old_fname
    new_path = data_dir / new_fname
    if old_path.exists() and old_path != new_path:
        old_path.rename(new_path)
    item["index"] = idx
    item["filename"] = new_fname
    new_items.append(item)

with open("scratch/harvested_generalization_candidates.json", "w", encoding="utf-8") as f:
    json.dump(new_items, f, indent=2)

print("Renamed files and updated json:")
for item in new_items:
    print(f"  {item['index']:02d}: {item['filename']}")
