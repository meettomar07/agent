import json
from pathlib import Path
import pymupdf

with open("scratch/candidates_found.json", "r", encoding="utf-8") as f:
    found = json.load(f)
found_hashes = {x["sha256"] for x in found}

# Load manifest hashes
manifest_files = [
    "DEVELOPMENT_SET_MANIFEST.json",
    "FROZEN_HELD_OUT_DATASET_MANIFEST.json",
    "GENERALIZATION_SET_MANIFEST.json",
    "NEW_VALIDATION_DATASET_MANIFEST.json",
    "PILOT_DATASET_MANIFEST.json",
    "VERIFICATION_SET_MANIFEST.json",
]
all_manifest_hashes = set()
for mf in manifest_files:
    data = json.loads(Path(mf).read_text(encoding="utf-8"))
    for k, doc in data.get("documents", {}).items():
        if "sha256" in doc and doc["sha256"]:
            all_manifest_hashes.add(doc["sha256"].lower().strip())

doc_dir = Path("data/documents")
other_files = [f for f in doc_dir.glob("*.pdf") if f.stem.lower() not in all_manifest_hashes and f.stem.lower() not in found_hashes]

print(f"Other unseen files: {len(other_files)}")
samples = []
for f in other_files[:30]:
    try:
        doc = pymupdf.open(str(f))
        txt = ""
        for p in doc[:2]:
            txt += p.get_text() + " "
        txt_clean = " ".join(txt.split())
        samples.append({
            "file": f.name,
            "pages": len(doc),
            "text_len": len(txt_clean),
            "sample": txt_clean[:120]
        })
    except Exception as e:
        samples.append({"file": f.name, "error": str(e)})

for s in samples[:15]:
    print(s)
