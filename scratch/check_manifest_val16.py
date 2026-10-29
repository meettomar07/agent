import json

with open('NEW_VALIDATION_DATASET_MANIFEST.json', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Find new_val_16
for notice in manifest.get('notices', []):
    fname = notice.get('file', '')
    if 'new_val_16' in fname:
        print(f"File: {fname}")
        gt = notice.get('ground_truth', {})
        print(f"Ground truth:")
        for k, v in gt.items():
            print(f"  {k}: {v!r}")
        break
else:
    # Try different structure
    print("Structure:", list(manifest.keys()))
    if isinstance(manifest, list):
        for item in manifest:
            if 'new_val_16' in str(item.get('file', '')):
                print(json.dumps(item, indent=2))
                break
