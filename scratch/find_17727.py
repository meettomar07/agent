from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from pathlib import Path

pdf_ext = PdfDocumentExtractor()
data = Path('data/new_validation_notices/new_val_51_ssc_tentative_vacancy_of_combined.pdf').read_bytes()
text, pages, cnt = pdf_ext.extract(data)
print(f"Total pages: {len(pages)}")
for p in pages:
    print(f"Page {p['page_number']}:")
    for line in p['text'].split('\n'):
        if '17727' in line or '17,727' in line or '10731' in line or '10,731' in line or 'total' in line.lower():
            print("  ", line)
