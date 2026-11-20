from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from pathlib import Path

content_51 = Path("data/new_validation_notices/new_val_51_ssc_tentative_vacancy_of_combined.pdf").read_bytes()
t51, p51, _ = PdfDocumentExtractor().extract(content_51)
print("Total pages extracted:", len(p51))
for p in p51:
    print(f"Page {p['page_number']} scanned: {p['is_scanned']}, conf: {p['ocr_confidence']}, text len: {len(p['text'])}")
    for l in p["text"].split("\n"):
        if "17727" in l or "17,727" in l or "GRAND" in l.upper():
            print("  [MATCH]:", l.strip())
