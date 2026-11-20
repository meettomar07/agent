from pathlib import Path
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.verifier import VerificationAgent

pdf_ext = PdfDocumentExtractor()
verifier = VerificationAgent()

fname = "new_val_01_tnpsc_combined_civil_services_examin.pdf"
content = Path("data/new_validation_notices", fname).read_bytes()
full_text, pages, count = pdf_ext.extract(content)
raw_facts = FactExtractor.extract_from_pages(
    pages, "Tamil Nadu Public Service Commission", fname, "https://official.gov.in/1"
)
v_facts = verifier._verify_and_cross_check_facts(raw_facts, full_text)
emitted = {f.key: f for f in v_facts if f.status == "VERIFIED"}

for k in ["recruiting_authority", "notice_number", "application_start_date", "application_end_date", "total_vacancies", "exam_date", "application_fee", "age_limit", "eligibility"]:
    item = emitted.get(k)
    print(f"{k:<25}: {item.value if item else 'N/A'} (status: {item.status if item else 'NONE'})")
