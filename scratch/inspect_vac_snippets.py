import pymupdf
import re

for doc_name in ["new_val_01_tnpsc_combined_civil_services_examin.pdf", "new_val_02_tnpsc_assistant_public_prosecutor__g.pdf", "new_val_38_upsc_notice__04_posts_of_homoeopath.html", "new_val_46_ssc_notification_for_recruitment_o.pdf"]:
    path = f"data/new_validation_notices/{doc_name}"
    if doc_name.endswith(".pdf"):
        doc = pymupdf.open(path)
        txt = "\n".join(page.get_text() for page in doc[:3])
        doc.close()
    else:
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read()
    print(f"\n=== {doc_name} ===")
    matches = [m.start() for m in re.finditer(r"vacanc|posts?", txt, re.IGNORECASE)]
    for pos in matches[:3]:
        snippet = txt[max(0, pos-40): min(len(txt), pos+80)].replace("\n", " ")
        print("  Snippet:", snippet)
