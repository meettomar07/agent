import json

with open("scratch/new_dataset_extracted_raw.json", "r", encoding="utf-8") as f:
    docs = json.load(f)

print(f"Total processed: {len(docs)}")
for i, d in enumerate(docs):
    scanned_str = "[SCANNED OCR]" if d["is_scanned"] else "[TEXT]"
    print(f"{i+1:02d}. {scanned_str} {d['authority'][:15]} | {d['file_name'][:45]} | chars: {d['chars']:6d}")
    # Show extracted facts summary
    facts_summary = ", ".join(f"{k}={v[:25]}" for k, v in d["extracted_facts"].items() if k not in ("recruiting_authority", "official_source_url"))
    if facts_summary:
        print(f"    Facts: {facts_summary}")
    else:
        print("    Facts: (None)")
