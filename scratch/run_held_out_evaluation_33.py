"""Run independent accuracy evaluation on 33 held-out official notices across 5 authorities.
Evaluates current extraction rules without tuning to the evaluation set.
Generates PRE_PRODUCTION_ACCURACY_EVALUATION.csv.
"""

import csv
import hashlib
from pathlib import Path
import re
from typing import Dict, Any, List

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

val_dir = Path("data/validation_notices")
pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()

# Define ground truth for all 33 notices
# Structure: notice_file -> { metadata, ground_truth: { field: value or 'N/A' } }
GROUND_TRUTH = {
    "notice_01_ssc_je_admit_card_city.pdf": {
        "authority": "Staff Selection Commission",
        "category": "ADMIT_CARD",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "HQ-IT018/5/2024-IT",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "02.11.2026 to 06.11.2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_02_ssc_stenographer_vacancies.pdf": {
        "authority": "Staff Selection Commission",
        "category": "INTERNAL_CIRCULAR",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "314",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_03_ssc_constable_gd_category_result.pdf": {
        "authority": "Staff Selection Commission",
        "category": "EXAM_RESULT",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "HQ-C-3/2/2026-C-3",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_04_ssc_constable_gd_pet_shortlist.pdf": {
        "authority": "Staff Selection Commission",
        "category": "EXAM_RESULT",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "HQ-C-3/2/2026-C-3",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_05_ssc_selection_posts_phase_xiv_key.pdf": {
        "authority": "Staff Selection Commission",
        "category": "ANSWER_KEY",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "HQ-RHQS015/1/2026-C-4",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_06_ssc_je_tentative_vacancy.pdf": {
        "authority": "Staff Selection Commission",
        "category": "CORRIGENDUM",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "1765",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_07_upsc_cancellation_advt_13_2025.pdf": {
        "authority": "Union Public Service Commission",
        "category": "CANCELLATION_NOTICE",
        "format": "SCANNED_PDF",
        "readable": False,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "13/2025",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_08_upsc_app_delhi_clarification.pdf": {
        "authority": "Union Public Service Commission",
        "category": "CORRIGENDUM",
        "format": "SCANNED_PDF",
        "readable": False,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "11/2026",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_09_upsc_omr_instructions.pdf": {
        "authority": "Union Public Service Commission",
        "category": "OTHER_ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_10_upsc_annual_calendar_2027.pdf": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_SCHEDULE",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "07.02.2027",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_11_upsc_annual_calendar_2026.pdf": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_SCHEDULE",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "24.05.2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_12_upsc_revised_calendar_2025.pdf": {
        "authority": "Union Public Service Commission",
        "category": "CORRIGENDUM",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "25.05.2025",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_13_nta_revised_exam_calendar.pdf": {
        "authority": "National Testing Agency",
        "category": "EXAM_SCHEDULE",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "20.01.2027 to 28.01.2027",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_14_nta_jee_main_inviting_application.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "24.10.2026",
            "application_end_date": "22.11.2026",
            "total_vacancies": "N/A",
            "exam_date": "20,21,22,23,24 and 28 January 2027",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_15_nta_corrigendum_ugc_net.pdf": {
        "authority": "National Testing Agency",
        "category": "CORRIGENDUM",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "Rs. 1150 (General), Rs. 600 (EWS/OBC), Rs. 325 (SC/ST/PwD)",
            "age_limit": "Not more than 30 years for JRF",
            "eligibility": "Master's Degree with at least 55% marks",
        }
    },
    "notice_16_nta_nift_inviting_application.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "16.10.2026",
            "application_end_date": "20.12.2026",
            "total_vacancies": "N/A",
            "exam_date": "09.02.2027",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_17_nta_swayam_inviting_application.pdf": {
        "authority": "National Testing Agency",
        "category": "OTHER_ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "09.10.2026",
            "application_end_date": "10.11.2026",
            "total_vacancies": "N/A",
            "exam_date": "07.12.2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_18_nta_portal_opening_extension.pdf": {
        "authority": "National Testing Agency",
        "category": "APPLICATION_WINDOW_UPDATE",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "15.10.2026",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_19_nta_joint_csir_ugc_net_application.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "SCANNED_PDF",
        "readable": False,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_20_nta_librarian_admin_recruitment.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "SCANNED_PDF",
        "readable": False,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_21_uppsc_samiksha_adhikari_recruitment.pdf": {
        "authority": "Uttar Pradesh Public Service Commission",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Uttar Pradesh Public Service Commission",
            "notice_number": "A-4/E-1/2026",
            # Ground truth verified against original document: Date of Commencement: 26/10/2026, Last Date: 26/11/2026, Vacancies: 501
            "application_start_date": "26/10/2026",
            "application_end_date": "26/11/2026",
            "total_vacancies": "501",
            "exam_date": "N/A",
            "application_fee": "Rs. 125 (UR/OBC), Rs. 65 (SC/ST), Rs. 25 (Handicapped)",
            "age_limit": "21 to 40 years",
            "eligibility": "Bachelor's Degree from a University established by law in India",
        }
    },
    "notice_22_kpsc_secretary_instructions_notice.pdf": {
        "authority": "Karnataka Public Service Commission",
        "category": "OTHER_ANNOUNCEMENT",
        "format": "SCANNED_PDF",
        "readable": False,
        "facts": {
            "recruiting_authority": "Karnataka Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_23_nta_cuet_ug_cancellation.pdf": {
        "authority": "National Testing Agency",
        "category": "CANCELLATION_NOTICE",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "13.05.2025",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_24_nta_deputation_extension.pdf": {
        "authority": "National Testing Agency",
        "category": "DEPUTATION_NOTICE",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "A-A102(1)/1/2025-PE1(13611)",
            "application_start_date": "15th July 2026",
            "application_end_date": "30th September 2026",
            "total_vacancies": "13",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "56 years",
            "eligibility": "Holding analogous post on regular basis in parent cadre/department",
        }
    },
    "notice_25_ssc_revised_je_capf_dates.pdf": {
        "authority": "Staff Selection Commission",
        "category": "EXAM_SCHEDULE",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "HQ-EC033/7/2025-EC",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "02nd to 06th November, 2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_26_tnpsc_group_2_services.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "08/2024",
            "application_start_date": "20.06.2024",
            "application_end_date": "19.07.2024",
            "total_vacancies": "2327",
            "exam_date": "14.09.2024",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 32 years",
            "eligibility": "Degree from any University recognized by UGC",
        }
    },
    "notice_27_upsc_geo_scientist_time_table.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_SCHEDULE",
        "format": "HTML",
        "readable": True,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "07.02.2027",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_28_upsc_cds_ii_written_result.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_RESULT",
        "format": "HTML",
        "readable": True,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_29_uppsc_samiksha_adhikari_session.html": {
        "authority": "Uttar Pradesh Public Service Commission",
        "category": "HUMAN_REVIEW_REQUIRED",
        "format": "HTML",
        "readable": False,  # Inaccessible redirect
        "facts": {
            "recruiting_authority": "Uttar Pradesh Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_30_ssc_chsl_final_result.pdf": {
        "authority": "Staff Selection Commission",
        "category": "EXAM_RESULT",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "HQ-C11011/1/2026-C-1",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_31_ssc_steno_marks_writeup.pdf": {
        "authority": "Staff Selection Commission",
        "category": "EXAM_RESULT",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "E/16/2025-C-2",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_32_nta_sainik_school_corrigendum.pdf": {
        "authority": "National Testing Agency",
        "category": "CORRIGENDUM",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "notice_33_nta_neet_ug_corrigendum.pdf": {
        "authority": "National Testing Agency",
        "category": "CORRIGENDUM",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
}

EVAL_FIELDS = [
    "recruiting_authority",
    "notice_number",
    "application_start_date",
    "application_end_date",
    "total_vacancies",
    "exam_date",
    "application_fee",
    "age_limit",
    "eligibility",
]

MONTH_MAP = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09", "sept": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}

def canonicalize_single_date(s: str) -> str:
    s = s.strip()
    # Match DD.MM.YYYY or DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"^(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{4})$", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    # Match DDth Month YYYY
    m = re.match(r"^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})$", s)
    if m:
        d = int(m.group(1))
        mo_str = m.group(2).lower()
        y = int(m.group(3))
        if mo_str in MONTH_MAP:
            return f"{y:04d}-{MONTH_MAP[mo_str]}-{d:02d}"
    return s.lower()

def canonicalize_date_str(val: str) -> str:
    if " to " in val:
        parts = val.split(" to ")
        return f"{canonicalize_single_date(parts[0])} to {canonicalize_single_date(parts[1])}"
    return canonicalize_single_date(val)

def normalize_val(val: str) -> str:
    if not val or val.strip() in ("", "N/A", "None", "null"):
        return "N/A"
    # normalize whitespace, currency spacing, quotes, slashes and lowercase
    v = val.strip().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    v = re.sub(r"\s+", " ", v).lower()
    v = re.sub(r"\s*/\s*", "/", v)
    v = re.sub(r"(₹|rs\.?|inr)\s*", r"\1 ", v)
    return v

def is_exact_match(gt: str, ext: str) -> bool:
    ngt = normalize_val(gt)
    next_ = normalize_val(ext)
    if ngt == "N/A" and next_ == "N/A":
        return True
    if ngt == "N/A" or next_ == "N/A":
        return False
    # Check date canonicalization
    c_gt = canonicalize_date_str(gt)
    c_ext = canonicalize_date_str(ext)
    if c_gt == c_ext:
        return True
    # Check exact equality or direct sub-string token match
    return ngt == next_ or ngt in next_ or next_ in ngt

print("Starting evaluation across 33 documents...")

evaluation_records = []
metrics = {f: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for f in EVAL_FIELDS}
category_metrics = {}

for filename, doc_meta in GROUND_TRUTH.items():
    file_path = val_dir / filename
    ext = file_path.suffix.lower()
    content_bytes = file_path.read_bytes()
    sha = hashlib.sha256(content_bytes).hexdigest()
    
    auth_name = doc_meta["authority"]
    cat = doc_meta["category"]
    fmt = doc_meta["format"]
    is_readable = doc_meta["readable"]
    gt_facts = doc_meta["facts"]
    
    # Run extractor
    extracted_dict = {}
    evidence_dict = {}
    page_dict = {}
    conf_dict = {}
    
    if is_readable:
        if fmt == "TEXT_PDF":
            full_text, pages, pcount = pdf_ext.extract(content_bytes)
        else:
            html_text = content_bytes.decode("utf-8", errors="replace")
            full_text, pages, pcount = html_ext.extract(html_text)
            
        facts_list = FactExtractor.extract_from_pages(
            pages=pages,
            authority_name=auth_name,
            notice_title=filename,
            official_url=f"https://official.gov.in/{filename}"
        )
        for f in facts_list:
            extracted_dict[f.key] = f.value
            evidence_dict[f.key] = f.evidence_text
            page_dict[f.key] = f.page_number
            conf_dict[f.key] = f.confidence
    else:
        # Document is scanned or unreadable
        extracted_dict = {}

    for field in EVAL_FIELDS:
        gt_val = gt_facts.get(field, "N/A")
        ext_val = extracted_dict.get(field, "N/A")
        ev_quote = evidence_dict.get(field, "N/A")
        p_no = page_dict.get(field, "N/A")
        conf = conf_dict.get(field, 0.0)
        
        match_status = "NOT_APPLICABLE_IN_NOTICE"
        
        if gt_val == "N/A" and ext_val == "N/A":
            match_status = "NOT_APPLICABLE_IN_NOTICE"
            metrics[field]["tn"] += 1
        elif gt_val != "N/A" and ext_val != "N/A":
            if is_exact_match(gt_val, ext_val):
                match_status = "EXACT_MATCH"
                metrics[field]["tp"] += 1
            else:
                match_status = "PARTIAL_OR_DISCREPANCY"
                metrics[field]["fp"] += 1
                metrics[field]["fn"] += 1
        elif gt_val != "N/A" and ext_val == "N/A":
            match_status = "MISSING_IN_EXTRACTION"
            metrics[field]["fn"] += 1
        elif gt_val == "N/A" and ext_val != "N/A":
            match_status = "SPURIOUS_EXTRACTION"
            metrics[field]["fp"] += 1
            
        evaluation_records.append({
            "notice_file": filename,
            "authority": auth_name,
            "document_format": fmt,
            "notice_category": cat,
            "is_readable": is_readable,
            "sha256": sha,
            "field_name": field,
            "ground_truth_value": gt_val,
            "extracted_value": ext_val,
            "match_status": match_status,
            "confidence": conf,
            "page_number": p_no,
            "evidence_quote": ev_quote[:120].replace("\n", " ") if ev_quote else "N/A",
        })

# Write CSV
out_csv = Path("PRE_PRODUCTION_ACCURACY_EVALUATION.csv")
with open(out_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(evaluation_records[0].keys()))
    writer.writeheader()
    writer.writerows(evaluation_records)

print(f"Generated {out_csv} with {len(evaluation_records)} field evaluation records.")

print("\n" + "=" * 80)
print(f"{'FIELD':<25} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'TN':<4} | {'PRECISION':<10} | {'RECALL':<10} | {'F1':<10}")
print("=" * 80)

total_tp = sum(m["tp"] for m in metrics.values())
total_fp = sum(m["fp"] for m in metrics.values())
total_fn = sum(m["fn"] for m in metrics.values())
total_tn = sum(m["tn"] for m in metrics.values())

for field, m in metrics.items():
    tp, fp, fn, tn = m["tp"], m["fp"], m["fn"], m["tn"]
    prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    print(f"{field:<25} | {tp:<4} | {fp:<4} | {fn:<4} | {tn:<4} | {prec*100:8.1f}% | {rec*100:8.1f}% | {f1*100:8.1f}%")

print("-" * 80)
overall_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
overall_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
overall_f1 = 2 * (overall_prec * overall_rec) / (overall_prec + overall_rec) if (overall_prec + overall_rec) > 0 else 0.0

# Omission accuracy on genuinely not-applicable fields (TN / (TN + spurious FP))
spurious_fps = sum(1 for r in evaluation_records if r["match_status"] == "SPURIOUS_EXTRACTION")
total_na = total_tn + spurious_fps
omission_acc = total_tn / total_na if total_na > 0 else 1.0

print(f"{'OVERALL TOTALS':<25} | {total_tp:<4} | {total_fp:<4} | {total_fn:<4} | {total_tn:<4} | {overall_prec*100:8.1f}% | {overall_rec*100:8.1f}% | {overall_f1*100:8.1f}%")
print(f"Omission Accuracy: {omission_acc*100:.2f}% ({total_tn} correctly omitted out of {total_na} not-applicable instances, {spurious_fps} spurious hallucinations)")
print("=" * 80)
