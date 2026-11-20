from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from pathlib import Path

pdf_ext = PdfDocumentExtractor()
data = Path("data/new_validation_notices/new_val_47_ssc_important_notice___schedule_of.pdf").read_bytes()
text, pages, cnt = pdf_ext.extract(data)
print(text)
