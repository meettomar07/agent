from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from pathlib import Path

pdf_ext = PdfDocumentExtractor()
data = Path('data/new_validation_notices/new_val_01_tnpsc_combined_civil_services_examin.pdf').read_bytes()
text, pages, cnt = pdf_ext.extract(data)
facts = FactExtractor.extract_from_pages(pages, 'Tamil Nadu Public Service Commission', 'test', 'http://test')
for f in facts:
    if 'end' in f.key or 'window' in f.key or 'start' in f.key:
        print(f.key, '->', f.value, '| ev:', f.evidence_text[:80])
