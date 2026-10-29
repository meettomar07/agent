import json

with open('NEW_VALIDATION_DATASET_MANIFEST.json', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

docs = manifest.get('documents', [])
print(f"Total documents: {len(docs)}")
print(f"Type of first doc: {type(docs[0])}")
if isinstance(docs[0], str):
    # documents is just a list of filenames
    for fname in docs:
        if any(n in fname for n in ['new_val_16', 'new_val_10', 'new_val_03', 'new_val_09']):
            print(f"  {fname}")
elif isinstance(docs[0], dict):
    for doc in docs:
        fname = str(doc)
        if any(n in fname for n in ['new_val_16', 'new_val_10', 'new_val_03', 'new_val_09']):
            print(json.dumps(doc, indent=2)[:500])
