from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from pathlib import Path

pdf_ext = PdfDocumentExtractor()
data = Path("data/new_validation_notices/new_val_50_ssc_important_notice__grade__c__st.pdf").read_bytes()
text, pages, cnt = pdf_ext.extract(data)
print("PAGES:", cnt)
for p in pages:
    print(p['text'])
