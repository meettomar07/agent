from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from pathlib import Path

pdf_ext = PdfDocumentExtractor()
data = Path('data/new_validation_notices/new_val_01_tnpsc_combined_civil_services_examin.pdf').read_bytes()
text, pages, cnt = pdf_ext.extract(data)

# Let's inspect pages[0]['text'] and pages[1]['text']
for p in pages[:2]:
    print(f"--- PAGE {p['page_number']} ---")
    for line in p['text'].split('\n'):
        if any(w in line.lower() for w in ['last date', 'closing', 'correction', '15.11', '19.11']):
            print("  ", line)
