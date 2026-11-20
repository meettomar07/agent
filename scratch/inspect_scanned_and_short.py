from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from pathlib import Path

pdf_ext = PdfDocumentExtractor()

print("--- new_val_47 text ---")
content_47 = Path("data/new_validation_notices/new_val_47_ssc_important_notice___schedule_of.pdf").read_bytes()
t47, p47, _ = pdf_ext.extract(content_47)
print(t47)

print("--- new_val_26 text ---")
content_26 = Path("data/new_validation_notices/new_val_26_nta_ugc_net_exam_june_2026___3__su.pdf").read_bytes()
t26, p26, _ = pdf_ext.extract(content_26)
print(t26[:1000])
