import json

with open('NEW_VALIDATION_DATASET_MANIFEST.json', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

docs = manifest.get('documents', {})
print(f"Type of documents: {type(docs)}")
if isinstance(docs, dict):
    for fname, doc_info in docs.items():
        if any(n in fname for n in ['new_val_16', 'new_val_10', 'new_val_03', 'new_val_09']):
            print(f"\nFile: {fname}")
            print(json.dumps(doc_info, indent=2)[:800])
elif isinstance(docs, list):
    first = docs[0] if docs else None
    print(f"First item type: {type(first)}")
    print(f"First item: {str(first)[:200]}")
