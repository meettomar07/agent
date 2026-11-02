import json
from pathlib import Path
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.classification.classifier import NoticeClassifier

pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()

# 1. Check rem_07
full_text, pages, _ = pdf_ext.extract(Path("data/remediation_evaluation_notices/rem_07_nta_swayam_july_semester_exam.pdf").read_bytes())
facts = FactExtractor.extract_from_pages(pages, "NTA", "SWAYAM", "url")
print("rem_07 facts:", {f.key: f.value for f in facts})

# 2. Check rem_15
full_text, pages, _ = pdf_ext.extract(Path("data/remediation_evaluation_notices/rem_15_tnpsc_departmental_promotion_circular.pdf").read_bytes())
facts = FactExtractor.extract_from_pages(pages, "TNPSC", "LDCE", "url")
print("rem_15 facts:", {f.key: f.value for f in facts})

# 3. Check which exam notice was OTHER_ANNOUNCEMENT
manifest = json.loads(Path("REMEDIATION_EVALUATION_MANIFEST.json").read_text(encoding="utf-8"))
for fname, meta in manifest["documents"].items():
    if "schedule" in fname or "dates" in fname:
        fpath = Path(meta["local_path"])
        if fname.endswith(".pdf"):
            full_text, pages, _ = pdf_ext.extract(fpath.read_bytes())
        else:
            full_text, pages, _ = html_ext.extract(fpath.read_text(encoding="utf-8"))
        snippet = " ".join(p.get("text", "") for p in pages[:2])
        cat = NoticeClassifier.classify(meta["title"], snippet, url=meta["source_url"], authority_name=meta["authority"])
        print(f"{fname}: {cat.value}")
