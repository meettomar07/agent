from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.table_extractor import TableExtractor, TableExtractionResult
from pathlib import Path

pdf_ext = PdfDocumentExtractor()
for doc_name in ['new_val_01_tnpsc_combined_civil_services_examin.pdf', 'new_val_02_tnpsc_assistant_public_prosecutor__g.pdf', 'new_val_03_tnpsc_combined_technical_services_ex.pdf']:
    data = Path(f'data/new_validation_notices/{doc_name}').read_bytes()
    text, pages, cnt = pdf_ext.extract(data)
    doc_tables = pages[0].get("document_tables", [])
    res = TableExtractionResult()
    for t in doc_tables:
        TableExtractor._parse_qualification_table(t, res)
    print(f"{doc_name[:20]}: res.eligibility = {res.eligibility}")
    print(f"  post_eligibility: {res.post_eligibility}")
