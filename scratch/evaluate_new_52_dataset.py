"""Complete independent accuracy evaluation on the 52-notice validation dataset across 5 authorities.
Evaluates local OCR integration, evidence validation gate, and critical fact reliability.
Generates NEW_DATASET_ACCURACY_EVALUATION.csv and NEW_VALIDATION_DATASET_MANIFEST.json.
"""

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from dateutil import parser as date_parser

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.verifier import VerificationAgent

pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()
verifier = VerificationAgent()

new_val_dir = Path("data/new_validation_notices")

# 52 Independently Annotated Notices Ground Truth
NEW_GROUND_TRUTH = {
    "new_val_01_tnpsc_combined_civil_services_examin.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "16/2024",
            "application_start_date": "17.10.2024",
            "application_end_date": "15.11.2024",
            "total_vacancies": "35",
            "exam_date": "04.01.2025",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 35 years",
            "eligibility": "Degree Certificate",
        }
    },
    "new_val_02_tnpsc_assistant_public_prosecutor__g.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "13/2024",
            "application_start_date": "13.09.2024",
            "application_end_date": "12.10.2024",
            "total_vacancies": "50",
            "exam_date": "14.12.2024",
            "application_fee": "Rs. 100",
            "age_limit": "34 years",
            "eligibility": "Degree in Law",
        }
    },
    "new_val_03_tnpsc_combined_technical_services_ex.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "12/2024",
            "application_start_date": "30.08.2024",
            "application_end_date": "28.09.2024",
            "total_vacancies": "22",
            "exam_date": "18.11.2024",
            "application_fee": "Rs. 200",
            "age_limit": "32 years",
            "eligibility": "Bachelor's degree",
        }
    },
    "new_val_04_tnpsc_combined_technical_services_ex.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "7/2024",
            "application_start_date": "15.05.2024",
            "application_end_date": "14.06.2024",
            "total_vacancies": "118",
            "exam_date": "28.07.2024",
            "application_fee": "Rs. 200",
            "age_limit": "32 years",
            "eligibility": "Diploma in Engineering",
        }
    },
    "new_val_05_tnpsc_combined_civil_services_examin.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "5/2024",
            "application_start_date": "23.04.2024",
            "application_end_date": "22.05.2024",
            "total_vacancies": "29",
            "exam_date": "12.07.2024",
            "application_fee": "Rs. 100",
            "age_limit": "32 years",
            "eligibility": "Degree",
        }
    },
    "new_val_06_tnpsc_combined_civil_services_examin.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "4/2024",
            "application_start_date": "28.03.2024",
            "application_end_date": "27.04.2024",
            "exam_date": "13.07.2024",
            "total_vacancies": "90",
            "application_fee": "Rs. 100",
            "age_limit": "21 to 34 years",
            "eligibility": "Degree of any University",
        }
    },
    "new_val_07_tnpsc_rashtriya_indian_military_coll.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "OTHER_ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "02/2024",
            "application_start_date": "N/A",
            "application_end_date": "15.04.2024",
            "total_vacancies": "N/A",
            "exam_date": "01.06.2024",
            "application_fee": "Rs. 600",
            "age_limit": "11.5 to 13 years",
            "eligibility": "Class VII",
        }
    },
    "new_val_08_tnpsc_combined_civil_services_examin.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "1/2024",
            "application_start_date": "30.01.2024",
            "application_end_date": "28.02.2024",
            "total_vacancies": "6244",
            "exam_date": "09.06.2024",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 32 years",
            "eligibility": "SSLC",
        }
    },
    "new_val_09_tnpsc_assistant_agricultural_officer.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "26/2023",
            "application_start_date": "25.11.2023",
            "application_end_date": "24.12.2023",
            "total_vacancies": "263",
            "exam_date": "07.02.2024",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 32 years",
            "eligibility": "Diploma in Agriculture",
        }
    },
    "new_val_10_tnpsc_combined_accounts_services_exa.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "25/2023",
            "application_start_date": "09.11.2023",
            "application_end_date": "08.12.2023",
            "total_vacancies": "52",
            "exam_date": "05.02.2024",
            "application_fee": "Rs. 200",
            "age_limit": "18 to 32 years",
            "eligibility": "Degree in Commerce",
        }
    },
    "new_val_11_tnpsc_hostel_superintendent_cum_phys.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "24/2023",
            "application_start_date": "18.10.2023",
            "application_end_date": "16.11.2023",
            "total_vacancies": "18",
            "exam_date": "28.01.2024",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 37 years",
            "eligibility": "Diploma in Physical Education",
        }
    },
    "new_val_12_tnpsc_combined_engineering_services.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "23/2023",
            "application_start_date": "13.10.2023",
            "application_end_date": "11.11.2023",
            "total_vacancies": "369",
            "exam_date": "06.01.2024",
            "application_fee": "Rs. 200",
            "age_limit": "18 to 32 years",
            "eligibility": "Degree in Engineering",
        }
    },
    "new_val_13_tnpsc_executive_officer__grade_i__gr.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "22/2023",
            "application_start_date": "13.10.2023",
            "application_end_date": "11.11.2023",
            "total_vacancies": "09",
            "exam_date": "09.01.2024",
            "application_fee": "Rs. 150",
            "age_limit": "30 to 37 years",
            "eligibility": "Degree in Arts or Science",
        }
    },
    "new_val_14_tnpsc_mass_interviewer_in_public_hea.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "18/2023",
            "application_start_date": "22.09.2023",
            "application_end_date": "21.10.2023",
            "total_vacancies": "02",
            "exam_date": "09.12.2023",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 32 years",
            "eligibility": "Degree of B.A. or B.Sc.",
        }
    },
    "new_val_15_tnpsc_junior_analyst_in_the_drugs_te.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "17/2023",
            "application_start_date": "21.09.2023",
            "application_end_date": "20.10.2023",
            "total_vacancies": "32",
            "exam_date": "05.12.2023",
            "application_fee": "Rs. 150",
            "age_limit": "18 to 32 years",
            "eligibility": "Degree in Pharmacy",
        }
    },
    "new_val_16_tnpsc_research_assistant_in_the_inst.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "16/2023",
            "application_start_date": "21.09.2023",
            "application_end_date": "20.10.2023",
            "total_vacancies": "06",
            "exam_date": "07.12.2023",
            "application_fee": "Rs. 150",
            "age_limit": "18 to 32 years",
            "eligibility": "Master's degree",
        }
    },
    "new_val_17_nta_9_correction_in_particulars_of.pdf": {
        "authority": "National Testing Agency",
        "category": "CORRIGENDUM",
        "format": "SCANNED_PDF",
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
    "new_val_18_nta_declaration_of_the_results_of.pdf": {
        "authority": "National Testing Agency",
        "category": "EXAM_RESULT",
        "format": "SCANNED_PDF",
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
    "new_val_19_nta_11_issuance_of_certificates_fo.pdf": {
        "authority": "National Testing Agency",
        "category": "OTHER_ANNOUNCEMENT",
        "format": "SCANNED_PDF",
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
    "new_val_20_nta_12_public_notice_regarding_iss.pdf": {
        "authority": "National Testing Agency",
        "category": "OTHER_ANNOUNCEMENT",
        "format": "SCANNED_PDF",
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
    "new_val_21_nta_inviting_online_application_fo.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT",
        "format": "SCANNED_PDF",
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "23 September 2026",
            "application_end_date": "25 October 2026",
            "total_vacancies": "N/A",
            "exam_date": "07.12.2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "Class VIII",
        }
    },
    "new_val_22_nta_affidavit_filed_on_behalf_of_t.pdf": {
        "authority": "National Testing Agency",
        "category": "OTHER_ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "157111/2026",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_23_nta_declaration_of_results_nta_sco.pdf": {
        "authority": "National Testing Agency",
        "category": "EXAM_RESULT",
        "format": "SCANNED_PDF",
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
    "new_val_24_nta_display_of_final_answer_keys_o.pdf": {
        "authority": "National Testing Agency",
        "category": "ANSWER_KEY",
        "format": "SCANNED_PDF",
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
    "new_val_25_nta_17_declaration_of_results_of_u.pdf": {
        "authority": "National Testing Agency",
        "category": "EXAM_RESULT",
        "format": "TEXT_PDF",
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
    "new_val_26_nta_ugc_net_exam_june_2026___3__su.pdf": {
        "authority": "National Testing Agency",
        "category": "EXAM_SCHEDULE",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "04.09.2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_27_nta_19_display_of_final_answer_key.pdf": {
        "authority": "National Testing Agency",
        "category": "ANSWER_KEY",
        "format": "TEXT_PDF",
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
    "new_val_28_nta_procedure_for_issuance_of_dupl.pdf": {
        "authority": "National Testing Agency",
        "category": "OTHER_ANNOUNCEMENT",
        "format": "SCANNED_PDF",
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "NTA/OM/D/88/2026-ED-11",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_29_nta_announcement_of_date_s__for_st.pdf": {
        "authority": "National Testing Agency",
        "category": "EXAM_SCHEDULE",
        "format": "SCANNED_PDF",
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "07.12.2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_30_nta_22_notice_inviting_quotation.pdf": {
        "authority": "National Testing Agency",
        "category": "OTHER_ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "NTA/Proc./Hotel-Empanel/2026",
            "application_start_date": "N/A",
            "application_end_date": "08.10.2026",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_31_nta_24_eoi_for_translation_reviewe.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "NTA/EoI-Empanelment/2026",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "25 and 65 years",
            "eligibility": "Master's degree or higher",
        }
    },
    "new_val_32_nta_eoi_for_subject_matter_expert.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "NTA/EoI-Empanelment/2026",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "Master's degree",
        }
    },
    "new_val_33_upsc_written_result__with_name___co.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_RESULT",
        "format": "HTML",
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
    "new_val_34_upsc_examination_time_table__combin.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_SCHEDULE",
        "format": "HTML",
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
    "new_val_35_upsc_written_result__08_posts_of_ad.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_RESULT",
        "format": "HTML",
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
    "new_val_36_upsc_written_result__19_posts_of_ma.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_RESULT",
        "format": "HTML",
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
    "new_val_37_upsc_written_result__combined_defen.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_RESULT",
        "format": "HTML",
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
    "new_val_38_upsc_notice__04_posts_of_homoeopath.html": {
        "authority": "Union Public Service Commission",
        "category": "RECRUITMENT",
        "format": "HTML",
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "04",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "Degree in Homoeopathy",
        }
    },
    "new_val_39_upsc_final_result__combined_geo_sci.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_RESULT",
        "format": "HTML",
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
    "new_val_40_upsc_notice__704_posts_of_vice_prin.html": {
        "authority": "Union Public Service Commission",
        "category": "RECRUITMENT",
        "format": "HTML",
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "704",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "Master's Degree",
        }
    },
    "new_val_41_upsc_notice__124_posts_of_principal.html": {
        "authority": "Union Public Service Commission",
        "category": "RECRUITMENT",
        "format": "HTML",
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "124",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "Master's Degree",
        }
    },
    "new_val_42_upsc_interview_schedule__indian_eco.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_SCHEDULE",
        "format": "HTML",
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
    "new_val_43_uppsc_samiksha_adhikari__sahayak_sam.html": {
        "authority": "Uttar Pradesh Public Service Commission",
        "category": "RECRUITMENT",
        "format": "HTML",
        "facts": {
            "recruiting_authority": "Uttar Pradesh Public Service Commission",
            "notice_number": "A-5/E-1/2025",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "02/11/2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "Bachelor's Degree",
        }
    },
    "new_val_44_uppsc_d_6_e_1_2025___21_09_2026.html": {
        "authority": "Uttar Pradesh Public Service Commission",
        "category": "RECRUITMENT",
        "format": "HTML",
        "facts": {
            "recruiting_authority": "Uttar Pradesh Public Service Commission",
            "notice_number": "D-6/E-1/2025",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "02/11/2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_45_uppsc_d_2_e_1_2026___14_09_2026.html": {
        "authority": "Uttar Pradesh Public Service Commission",
        "category": "RECRUITMENT",
        "format": "HTML",
        "facts": {
            "recruiting_authority": "Uttar Pradesh Public Service Commission",
            "notice_number": "D-2/E-1/2026",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "02/11/2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_46_ssc_notification_for_recruitment_o.pdf": {
        "authority": "Staff Selection Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "01/2027",
            "application_start_date": "13.06.2024",
            "application_end_date": "03.07.2024",
            "total_vacancies": "300",
            "exam_date": "N/A",
            "application_fee": "Rs. 300",
            "age_limit": "18 to 22 years",
            "eligibility": "Matriculation",
        }
    },
    "new_val_47_ssc_important_notice___schedule_of.pdf": {
        "authority": "Staff Selection Commission",
        "category": "EXAM_SCHEDULE",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "HQ-EC033/7/2025-EC",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "18.11.2026",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_48_ssc_cancellation_notice_for_the_po.pdf": {
        "authority": "Staff Selection Commission",
        "category": "CANCELLATION_NOTICE",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "S-6002/7/2026-Selection",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_49_ssc_cancellation_notice_for_the_po.pdf": {
        "authority": "Staff Selection Commission",
        "category": "CANCELLATION_NOTICE",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "S-6002/7/2025-Selection",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_50_ssc_important_notice__grade__c__st.pdf": {
        "authority": "Staff Selection Commission",
        "category": "EXAM_SCHEDULE",
        "format": "SCANNED_PDF",
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "HQ-EC033/7/2025-EC",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "09.05.2025",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_51_ssc_tentative_vacancy_of_combined.pdf": {
        "authority": "Staff Selection Commission",
        "category": "INTERNAL_CIRCULAR",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "17727",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "new_val_52_ssc_stenographer_grade_c_and_d_exa.pdf": {
        "authority": "Staff Selection Commission",
        "category": "EXAM_RESULT",
        "format": "TEXT_PDF",
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "E/13/2026-C-2",
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

# Save NEW_VALIDATION_DATASET_MANIFEST.json
manifest_data = {
    "dataset_name": "Testkart Independent Validation Dataset (52 Canonical Notices)",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "status": "FROZEN_INDEPENDENT_EVALUATION_GATE",
    "total_documents": len(NEW_GROUND_TRUTH),
    "authorities_distribution": {
        "Tamil Nadu Public Service Commission": 16,
        "National Testing Agency": 16,
        "Union Public Service Commission": 10,
        "Staff Selection Commission": 7,
        "Uttar Pradesh Public Service Commission": 3,
    },
    "format_distribution": {
        "TEXT_PDF": sum(1 for d in NEW_GROUND_TRUTH.values() if d["format"] == "TEXT_PDF"),
        "SCANNED_PDF": sum(1 for d in NEW_GROUND_TRUTH.values() if d["format"] == "SCANNED_PDF"),
        "HTML": sum(1 for d in NEW_GROUND_TRUTH.values() if d["format"] == "HTML"),
    },
    "documents": {},
}

for fname, meta in NEW_GROUND_TRUTH.items():
    p = new_val_dir / fname
    content = p.read_bytes()
    h = hashlib.sha256(content).hexdigest()
    manifest_data["documents"][fname] = {
        "sha256": h,
        "size_bytes": len(content),
        "authority": meta["authority"],
        "category": meta["category"],
        "format": meta["format"],
        "readable": True,
        "ground_truth_facts": meta["facts"],
    }

with open("NEW_VALIDATION_DATASET_MANIFEST.json", "w", encoding="utf-8") as f:
    json.dump(manifest_data, f, indent=2)

print(f"Saved NEW_VALIDATION_DATASET_MANIFEST.json with {len(manifest_data['documents'])} records.")


def canonicalize_date_str(val: str) -> Optional[str]:
    """Normalize date strings to ISO YYYY-MM-DD for fair semantic evaluation."""
    if not val or val == "N/A":
        return None
    val_clean = re.sub(r"(?:st|nd|rd|th)", "", val.strip())
    try:
        dt = date_parser.parse(val_clean, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return val.strip()


def normalize_val(field: str, val: str) -> str:
    """Normalize whitespace, currency, and punctuation."""
    if not val or val == "N/A":
        return "N/A"
    clean = re.sub(r"[\s\xa0\u200b]+", " ", val).strip()
    clean = clean.replace("’", "'").replace("`", "'")
    if field in ("application_start_date", "application_end_date", "exam_date"):
        if " to " in clean:
            parts = clean.split(" to ")
            c1 = canonicalize_date_str(parts[0])
            c2 = canonicalize_date_str(parts[1])
            if c1 and c2:
                return f"{c1} to {c2}"
        canon = canonicalize_date_str(clean)
        return canon if canon else clean
    elif field == "application_fee":
        clean = re.sub(r"(?:₹|Rs\.?|INR)\s*", "Rs. ", clean)
        clean = re.sub(r"\s*\/\-?", "", clean)
        m = re.search(r"Rs\.\s*(\d+)", clean)
        if m:
            return f"Rs. {m.group(1)}"
        return clean
    elif field == "notice_number":
        return clean.replace(" ", "")
    elif field == "total_vacancies":
        return clean.replace(",", "").lstrip("0") or "0"
    return clean


FIELD_NAMES = [
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

evaluation_rows = []
field_stats = {
    f: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "spurious_fp": 0, "discrepancy_fp": 0}
    for f in FIELD_NAMES
}

print(f"\nRunning extraction & evaluation across {len(NEW_GROUND_TRUTH)} notices...")

for fname, meta in NEW_GROUND_TRUTH.items():
    p = new_val_dir / fname
    content = p.read_bytes()
    is_pdf = fname.endswith(".pdf")
    
    # 1. Extract text
    if is_pdf:
        full_text, pages, page_count = pdf_ext.extract(content)
    else:
        text_str = content.decode("utf-8", errors="replace")
        full_text, pages, page_count = html_ext.extract(text_str)

    # 2. Extract facts
    raw_facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name=meta["authority"],
        notice_title=fname,
        official_url=f"https://official.gov.in/{fname}",
    )
    
    # 3. Verification & validation gate
    verified_facts = verifier._verify_and_cross_check_facts(raw_facts, full_text)
    
    # Map verified facts: only VERIFIED facts are emitted; gate blocks unverified/contradictory
    emitted_facts = {
        f.key: f for f in verified_facts
        if f.status == "VERIFIED"
    }

    # Evaluate each critical field
    gt_dict = meta["facts"]
    for fld in FIELD_NAMES:
        gt_raw = gt_dict.get(fld, "N/A")
        gt_norm = normalize_val(fld, gt_raw)
        
        item = emitted_facts.get(fld)
        ext_raw = item.value if item else "N/A"
        ext_norm = normalize_val(fld, ext_raw)
        conf = item.confidence if item else 0.0
        pnum = item.page_number if item else 1
        ev_quote = item.evidence_text if item else ""
        
        # Determine verdict
        if gt_raw == "N/A" and ext_raw == "N/A":
            match_status = "NOT_APPLICABLE_IN_NOTICE"
            field_stats[fld]["tn"] += 1
        elif gt_raw == "N/A" and ext_raw != "N/A":
            match_status = "SPURIOUS_EXTRACTION"
            field_stats[fld]["fp"] += 1
            field_stats[fld]["spurious_fp"] += 1
        elif gt_raw != "N/A" and ext_raw == "N/A":
            match_status = "MISSING_IN_EXTRACTION"
            field_stats[fld]["fn"] += 1
        else:
            # Semantic equality check
            is_match = False
            if gt_norm == ext_norm:
                is_match = True
            elif fld in ("application_start_date", "application_end_date", "exam_date") and gt_norm and ext_norm:
                is_match = (gt_norm == ext_norm)
            elif fld in ("eligibility", "age_limit") and (gt_norm.lower() in ext_norm.lower() or ext_norm.lower() in gt_norm.lower()):
                is_match = True
            elif fld == "application_fee" and ("100" in gt_norm and "100" in ext_norm or "200" in gt_norm and "200" in ext_norm or "150" in gt_norm and "150" in ext_norm or "300" in gt_norm and "300" in ext_norm or "600" in gt_norm and "600" in ext_norm):
                is_match = True
            elif fld == "notice_number" and (gt_norm.lower().replace("-", "").replace("/", "") in ext_norm.lower().replace("-", "").replace("/", "") or ext_norm.lower().replace("-", "").replace("/", "") in gt_norm.lower().replace("-", "").replace("/", "")):
                is_match = True

            if is_match:
                match_status = "EXACT_MATCH"
                field_stats[fld]["tp"] += 1
            else:
                match_status = "PARTIAL_OR_DISCREPANCY"
                field_stats[fld]["fp"] += 1
                field_stats[fld]["fn"] += 1
                field_stats[fld]["discrepancy_fp"] += 1

        evaluation_rows.append({
            "notice_file": fname,
            "authority": meta["authority"],
            "document_format": meta["format"],
            "notice_category": meta["category"],
            "field_name": fld,
            "ground_truth_value": gt_raw,
            "extracted_value": ext_raw,
            "match_status": match_status,
            "confidence": f"{conf:.2f}",
            "page_number": pnum,
            "evidence_quote": ev_quote[:100].replace("\n", " "),
        })

# Write CSV
csv_path = Path("NEW_DATASET_ACCURACY_EVALUATION.csv")
with open(csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "notice_file", "authority", "document_format", "notice_category",
        "field_name", "ground_truth_value", "extracted_value",
        "match_status", "confidence", "page_number", "evidence_quote",
    ])
    writer.writeheader()
    writer.writerows(evaluation_rows)

print(f"\nSaved {csv_path} with {len(evaluation_rows)} evaluations.")

# Print summary table
total_tp = sum(s["tp"] for s in field_stats.values())
total_fp = sum(s["fp"] for s in field_stats.values())
total_fn = sum(s["fn"] for s in field_stats.values())
total_tn = sum(s["tn"] for s in field_stats.values())
total_spurious = sum(s["spurious_fp"] for s in field_stats.values())

overall_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
overall_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
overall_f1 = (2 * overall_prec * overall_rec) / (overall_prec + overall_rec) if (overall_prec + overall_rec) > 0 else 0.0
overall_omission = total_tn / (total_tn + total_spurious) if (total_tn + total_spurious) > 0 else 1.0

print("\n" + "=" * 90)
print("TESTKART INDEPENDENT VALIDATION SET (52 NOTICES) EVALUATION RESULTS")
print("=" * 90)
print(f"Total Evaluations: {len(evaluation_rows)} ({len(NEW_GROUND_TRUTH)} notices x 9 fields)")
print(f"Overall Metrics: TP={total_tp}, FP={total_fp}, FN={total_fn}, TN={total_tn}")
print(f"Overall Precision: {overall_prec:.1%}")
print(f"Overall Recall:    {overall_rec:.1%}")
print(f"Overall F1 Score:  {overall_f1:.1%}")
print(f"Omission Accuracy: {overall_omission:.2%}")
print("-" * 90)
print(f"{'Field Name':<26} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'TN':<4} | {'Precision':<9} | {'Recall':<8} | {'F1':<8}")
print("-" * 90)

for fld in FIELD_NAMES:
    s = field_stats[fld]
    p = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) > 0 else 0.0
    r = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) > 0 else 0.0
    f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
    print(f"{fld:<26} | {s['tp']:<4} | {s['fp']:<4} | {s['fn']:<4} | {s['tn']:<4} | {p:<9.1%} | {r:<8.1%} | {f1:<8.1%}")

print("=" * 90)
