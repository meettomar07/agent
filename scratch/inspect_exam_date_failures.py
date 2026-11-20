import sys
from pathlib import Path
from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()

val_dir = Path("data/new_validation_notices")

exam_fails = [
    ("new_val_09_tnpsc_assistant_agricultural_officer.pdf", "07.02.2024", "Tamil Nadu Public Service Commission"),
    ("new_val_10_tnpsc_combined_accounts_services_exa.pdf", "05.02.2024", "Tamil Nadu Public Service Commission"),
    ("new_val_11_tnpsc_hostel_superintendent_cum_phys.pdf", "28.01.2024", "Tamil Nadu Public Service Commission"),
    ("new_val_12_tnpsc_combined_engineering_services.pdf", "06.01.2024", "Tamil Nadu Public Service Commission"),
    ("new_val_13_tnpsc_executive_officer__grade_i__gr.pdf", "09.01.2024", "Tamil Nadu Public Service Commission"),
    ("new_val_14_tnpsc_mass_interviewer_in_public_hea.pdf", "09.12.2023", "Tamil Nadu Public Service Commission"),
    ("new_val_15_tnpsc_junior_analyst_in_the_drugs_te.pdf", "05.12.2023", "Tamil Nadu Public Service Commission"),
    ("new_val_16_tnpsc_research_assistant_in_the_inst.pdf", "07.12.2023", "Tamil Nadu Public Service Commission"),
    ("new_val_21_nta_inviting_online_application_fo.pdf", "07.12.2026", "National Testing Agency"),
    ("new_val_26_nta_ugc_net_exam_june_2026___3__su.pdf", "04.09.2026", "National Testing Agency"),
    ("new_val_29_nta_announcement_of_date_s__for_st.pdf", "07.12.2026", "National Testing Agency"),
    ("new_val_34_upsc_examination_time_table__combin.html", "07.02.2027", "Union Public Service Commission"),
    ("new_val_47_ssc_important_notice___schedule_of.pdf", "18.11.2026", "Staff Selection Commission"),
    ("new_val_50_ssc_important_notice__grade__c__st.pdf", "09.05.2025", "Staff Selection Commission"),
]

for fname, exp, auth in exam_fails:
    fpath = val_dir / fname
    print(f"\n{'='*20} {fname} (Expected: {exp}) {'='*20}")
    content = fpath.read_bytes()
    if fname.endswith(".html"):
        full_text, pages, count = html_ext.extract(content.decode("utf-8", errors="replace"))
    else:
        full_text, pages, count = pdf_ext.extract(content)
    
    found_in_pages = [p["page_number"] for p in pages if exp in p["text"]]
    print(f"Total pages: {count} | Expected '{exp}' in pages: {found_in_pages}")
    
    raw_facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name=auth,
        notice_title=fname,
        official_url=f"https://official.gov.in/{fname}"
    )
    ed_facts = [f for f in raw_facts if f.key == "exam_date"]
    print(f"Extracted exam_date raw facts count: {len(ed_facts)}")
    for f in ed_facts:
        print(f"  Raw: {f.value} | Norm: {getattr(f, 'normalized_value', None)} | Status: {f.status} | Conf: {f.confidence}")
        print(f"  Evidence: {f.evidence_text[:120]}")
    
    # Also print any line containing the date or year in first 2 pages
    if not found_in_pages:
        d, m, y = exp.split(".") if "." in exp else exp.split("/")
        for p in pages[:2]:
            for line in p["text"].split("\n"):
                if y in line and any(k in line.lower() for k in ["exam", "paper", "cbt", "written", "test", "date", "stage"]):
                    print(f"  [P{p['page_number']} candidate line]: {line.strip()[:100]}")
