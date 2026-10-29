import json

with open('NEW_VALIDATION_DATASET_MANIFEST.json', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Structure uses 'documents' key
for doc in manifest.get('documents', []):
    fname = doc.get('file', doc.get('filename', ''))
    if 'new_val_16' in fname or 'new_val_10' in fname or 'new_val_03' in fname or 'new_val_09' in fname:
        print(f"\nFile: {fname}")
        gt = doc.get('ground_truth', {})
        vac = gt.get('total_vacancies', 'NOT IN GT')
        print(f"  total_vacancies GT: {vac!r}")
        # Print all fields
        for k, v in gt.items():
            print(f"  {k}: {v!r}")
