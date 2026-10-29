"""Evaluate FactExtractor against ground truth for 22 real government notifications."""

import os
import glob
import csv
import hashlib
from typing import Dict, Any, List

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

# Ground truth dictionary for the 22 validation notices
GROUND_TRUTH = {
    "notice_01_ssc_je_admit_card_city.pdf": {
        "authority": "Staff Selection Commission",
        "exam_name": "Junior Engineer Examination, 2026 (CBE) Paper-I",
        "notice_number": "HQ-IT018/5/2024-IT",
        "category": "ADMIT_CARD",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": "02.11.2026 to 06.11.2026",
    },
    "notice_02_ssc_stenographer_vacancies.pdf": {
        "authority": "Staff Selection Commission",
        "exam_name": "Grade 'C' Stenographers LDCE, 2025",
        "notice_number": None,
        "category": "ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "total_vacancies": "314",
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": None,
    },
    "notice_03_ssc_constable_gd_category_result.pdf": {
        "authority": "Staff Selection Commission",
        "exam_name": "Constable (GD) in Central Armed Police Forces (CAPFs) and SSF, and Rifleman (GD) in Assam Rifles Examination, 2026",
        "notice_number": "HQ-C-3/2/2026-C-3",
        "category": "RESULT_ANSWER_KEY",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": "12.10.2026",
    },
    "notice_04_ssc_constable_gd_pet_shortlist.pdf": {
        "authority": "Staff Selection Commission",
        "exam_name": "Constable (GD) in Central Armed Police Forces (CAPFs) and SSF, and Rifleman (GD) in Assam Rifles Examination, 2026",
        "notice_number": "HQ-C-3/2/2026-C-3",
        "category": "RESULT_ANSWER_KEY",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": "27.04.2026 to 30.05.2026",
    },
    "notice_05_ssc_selection_posts_phase_xiv_key.pdf": {
        "authority": "Staff Selection Commission",
        "exam_name": "Phase-XIV/2026/Selection Posts Examination",
        "notice_number": "HQ-RHQS015/1/2026-C-4",
        "category": "RESULT_ANSWER_KEY",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": None,
        "end_date": None,
        "fee": "₹50/- per question/answer challenged",
        "age_limit": None,
        "eligibility": "Matriculation, Higher Secondary (10+2) and Graduation & Above",
        "exam_date": "16.09.2026 to 26.09.2026",
    },
    "notice_06_ssc_je_tentative_vacancy.pdf": {
        "authority": "Staff Selection Commission",
        "exam_name": "Junior Engineer (Civil, Mechanical & Electrical) Examination, 2024",
        "notice_number": None,
        "category": "CORRIGENDUM",
        "format": "TEXT_PDF",
        "total_vacancies": "1765",
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": None,
    },
    "notice_07_upsc_cancellation_advt_13_2025.pdf": {
        "authority": "Union Public Service Commission",
        "exam_name": "Six (06) Posts in Ministry of Mines advertised vide Advt. No. 13-2025",
        "notice_number": "13-2025",
        "category": "CORRIGENDUM",
        "format": "SCANNED_PDF",
        "total_vacancies": "6",
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": None,
    },
    "notice_08_upsc_app_delhi_clarification.pdf": {
        "authority": "Union Public Service Commission",
        "exam_name": "Assistant Public Prosecutor in Directorate of Prosecution, Home Dept GNCTD",
        "notice_number": "11-2026",
        "category": "CORRIGENDUM",
        "format": "SCANNED_PDF",
        "total_vacancies": None,
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": "Degree in Law with 3 years experience at the Bar",
        "exam_date": None,
    },
    "notice_09_upsc_omr_instructions.pdf": {
        "authority": "Union Public Service Commission",
        "exam_name": "Common Mistakes Done While Filling OMR Sheet / Scannable Attendance List",
        "notice_number": None,
        "category": "ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": None,
    },
    "notice_10_upsc_annual_calendar_2027.pdf": {
        "authority": "Union Public Service Commission",
        "exam_name": "Programme of Examinations / Recruitment Tests (RTs) - 2027",
        "notice_number": None,
        "category": "ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": "02.09.2026",
        "end_date": "22.09.2026",
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": "10.01.2027",
    },
    "notice_11_upsc_annual_calendar_2026.pdf": {
        "authority": "Union Public Service Commission",
        "exam_name": "Programme of Examinations / Recruitment Tests (RTs) - 2026",
        "notice_number": None,
        "category": "ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": "03.09.2025",
        "end_date": "23.09.2025",
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": "08.02.2026",
    },
    "notice_12_upsc_revised_calendar_2025.pdf": {
        "authority": "Union Public Service Commission",
        "exam_name": "Revised - III Programme of Examinations - 2025",
        "notice_number": None,
        "category": "CORRIGENDUM",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": "18.10.2024",
        "end_date": "22.11.2024",
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": "27.04.2025",
    },
    "notice_13_nta_revised_exam_calendar.pdf": {
        "authority": "National Testing Agency",
        "exam_name": "Examination Calendar December 2026 Cycle onwards",
        "notice_number": None,
        "category": "ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": "06 Dec 2026",
    },
    "notice_14_nta_jee_main_inviting_application.pdf": {
        "authority": "National Testing Agency",
        "exam_name": "Joint Entrance Examination (Main) – 2027 (Session 1)",
        "notice_number": None,
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": "24th October 2026",
        "end_date": "22nd November 2026",
        "fee": None,
        "age_limit": None,
        "eligibility": "10+2 / Higher Secondary with Physics, Mathematics",
        "exam_date": "22 January 2027 to 31 January 2027",
    },
    "notice_15_nta_corrigendum_ugc_net.pdf": {
        "authority": "National Testing Agency",
        "exam_name": "UGC - NET December 2026 Information Bulletin",
        "notice_number": None,
        "category": "CORRIGENDUM",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": "08.10.2026",
        "end_date": "07.11.2026",
        "fee": "General: Rs. 1150/-, Gen-EWS/OBC-NCL: Rs. 600/-, SC/ST/PwD: Rs. 325/-",
        "age_limit": "JRF: Not more than 30 years as on 01.12.2026",
        "eligibility": "Master's Degree with minimum 55% marks (50% for SC/ST/OBC)",
        "exam_date": "01 January 2027 to 19 January 2027",
    },
    "notice_16_nta_nift_inviting_application.pdf": {
        "authority": "National Testing Agency",
        "exam_name": "National Institute of Fashion Technology Entrance Examination (NIFTEE)–2027",
        "notice_number": None,
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": "22.10.2026",
        "end_date": "06.01.2027",
        "fee": None,
        "age_limit": None,
        "eligibility": "10+2 or equivalent examination for UG Programmes",
        "exam_date": "10th January 2027",
    },
    "notice_17_nta_swayam_inviting_application.pdf": {
        "authority": "National Testing Agency",
        "exam_name": "Study Webs of Active Learning for Young Aspiring Minds (SWAYAM-2026 July Semester)",
        "notice_number": None,
        "category": "ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": "09.10.2026",
        "end_date": "31.10.2026",
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": "08.12.2026 to 12.12.2026",
    },
    "notice_18_nta_portal_opening_extension.pdf": {
        "authority": "National Testing Agency",
        "exam_name": "UGC-NET December 2026",
        "notice_number": None,
        "category": "ANNOUNCEMENT",
        "format": "TEXT_PDF",
        "total_vacancies": None,
        "start_date": "08 October 2026",
        "end_date": "07 November 2026",
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": "14 December 2026 to 19 December 2026",
    },
    "notice_19_nta_joint_csir_ugc_net_application.pdf": {
        "authority": "National Testing Agency",
        "exam_name": "Joint CSIR - UGC NET December 2026",
        "notice_number": None,
        "category": "ANNOUNCEMENT",
        "format": "SCANNED_PDF",
        "total_vacancies": None,
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": "M.Sc. or equivalent degree with 55% marks",
        "exam_date": "19, 22 and 27 December 2026",
    },
    "notice_20_nta_librarian_admin_recruitment.pdf": {
        "authority": "National Testing Agency",
        "exam_name": "Librarian - Administration Direct Recruitment",
        "notice_number": "01/2026",
        "category": "RECRUITMENT",
        "format": "SCANNED_PDF",
        "total_vacancies": "1",
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": "Maximum 56 years on closing date",
        "eligibility": "Master's Degree in Library Science/Information Science",
        "exam_date": None,
    },
    "notice_21_uppsc_samiksha_adhikari_recruitment.pdf": {
        "authority": "Uttar Pradesh Public Service Commission",
        "exam_name": "Samiksha Adhikari / Sahayak Samiksha Adhikari (RO/ARO) Examination",
        "notice_number": "A-4/E-1/2026",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "total_vacancies": "411",
        "start_date": "26/10/2026",
        "end_date": "26/11/2026",
        "fee": "Unreserved/OBC: Rs. 125/-, SC/ST: Rs. 65/-, PwD: Rs. 25/-",
        "age_limit": "21 to 40 years as on 01/07/2026",
        "eligibility": "Bachelor's Degree of a University established by law in India",
        "exam_date": None,
    },
    "notice_22_kpsc_secretary_instructions_notice.pdf": {
        "authority": "Karnataka Public Service Commission",
        "exam_name": "General Instructions to Candidates as on 17-10-2026",
        "notice_number": "PSC 101 RT(1)/2026",
        "category": "ANNOUNCEMENT",
        "format": "SCANNED_PDF",
        "total_vacancies": None,
        "start_date": None,
        "end_date": None,
        "fee": None,
        "age_limit": None,
        "eligibility": None,
        "exam_date": None,
    },
}

HELD_OUT_FILES = {
    "notice_01_ssc_je_admit_card_city.pdf",
    "notice_03_ssc_constable_gd_category_result.pdf",
    "notice_10_upsc_annual_calendar_2027.pdf",
    "notice_13_nta_revised_exam_calendar.pdf",
    "notice_16_nta_nift_inviting_application.pdf",
    "notice_17_nta_swayam_inviting_application.pdf",
}

extractor = PdfDocumentExtractor()
evaluation_rows = []

fields_to_eval = [
    ("recruiting_authority", "authority"),
    ("notice_number", "notice_number"),
    ("total_vacancies", "total_vacancies"),
    ("application_start_date", "start_date"),
    ("application_end_date", "end_date"),
    ("exam_date", "exam_date"),
    ("application_fee", "fee"),
    ("age_limit", "age_limit"),
    ("eligibility", "eligibility"),
]

exact_matches = 0
partial_matches = 0
missing_in_extraction = 0
incorrect_values = 0
not_applicable_count = 0
flagged_scanned = 0
total_evaluated_fields = 0

for filename, gt in GROUND_TRUTH.items():
    fpath = os.path.join("data/validation_notices", filename)
    with open(fpath, "rb") as f:
        content = f.read()
    
    sha256 = hashlib.sha256(content).hexdigest()
    full_text, pages, pcount = extractor.extract(content)
    is_scanned = any("SCANNED DOCUMENT" in p.get("text", "") for p in pages)
    subset_label = "HELD_OUT_VALIDATION_SET" if filename in HELD_OUT_FILES else "DEVELOPMENT_SET"
    
    extracted_items = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name=gt["authority"],
        notice_title=gt["exam_name"],
        official_url=f"https://official.gov.in/{filename}",
    )
    
    extracted_dict = {item.key: item for item in extracted_items}
    
    for fact_key, gt_key in fields_to_eval:
        total_evaluated_fields += 1
        gt_val = gt[gt_key]
        ext_item = extracted_dict.get(fact_key)
        ext_val = ext_item.value if ext_item else None
        
        status = ""
        notes = ""
        
        if is_scanned:
            flagged_scanned += 1
            if gt_val is not None:
                status = "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW"
                notes = "Document is scanned image; automated OCR not configured; flagged for human verification"
            else:
                status = "NOT_APPLICABLE_IN_NOTICE"
                notes = "Field not present in notice"
                not_applicable_count += 1
        elif gt_val is None:
            if ext_val is None:
                status = "NOT_APPLICABLE_IN_NOTICE"
                notes = "Correctly omitted (field not present in official notice)"
                not_applicable_count += 1
            else:
                status = "SPURIOUS_EXTRACTION"
                incorrect_values += 1
                notes = f"Model extracted '{ext_val}' but field is not in notice"
        else:
            # Ground truth exists
            if ext_val is None:
                status = "MISSING_IN_EXTRACTION"
                missing_in_extraction += 1
                notes = f"Ground truth '{gt_val}' was missed by regex/pattern rules"
            else:
                # Compare values
                gt_clean = str(gt_val).lower().replace(" ", "").replace("-", "").replace("/", "")
                ext_clean = str(ext_val).lower().replace(" ", "").replace("-", "").replace("/", "")
                
                # Semantic date matching
                dates_matched = False
                try:
                    from dateutil import parser as dparser
                    d_gt = dparser.parse(str(gt_val), dayfirst=True)
                    d_ext = dparser.parse(str(ext_val), dayfirst=True)
                    if d_gt.date() == d_ext.date():
                        dates_matched = True
                except Exception:
                    pass

                if gt_clean == ext_clean or gt_val == ext_val or dates_matched:
                    status = "EXACT_MATCH"
                    exact_matches += 1
                    if fact_key == "recruiting_authority":
                        notes = f"Metadata pass-through (echoed from caller argument, not extracted from document text): '{ext_val}'"
                    elif dates_matched:
                        notes = f"Exact semantic date match: '{ext_val}' == '{gt_val}'"
                    else:
                        notes = f"Exact match with official evidence: '{ext_val}'"
                elif gt_clean in ext_clean or ext_clean in gt_clean:
                    status = "PARTIAL_MATCH"
                    partial_matches += 1
                    notes = f"Partial/sub-phrase match (Extracted: '{ext_val}' vs Truth: '{gt_val}')"
                else:
                    status = "INCORRECT_VALUE"
                    incorrect_values += 1
                    notes = f"Extracted value '{ext_val}' differs from verified truth '{gt_val}'"
        
        evaluation_rows.append({
            "notice_file": filename,
            "evaluation_subset": subset_label,
            "authority": gt["authority"],
            "document_format": gt["format"],
            "notice_category": gt["category"],
            "sha256": sha256,
            "field_name": fact_key,
            "ground_truth_value": str(gt_val) if gt_val is not None else "N/A",
            "extracted_value": str(ext_val) if ext_val is not None else "N/A",
            "match_status": status,
            "confidence": ext_item.confidence if ext_item else 0.0,
            "page_number": ext_item.page_number if ext_item else (1 if is_scanned else "N/A"),
            "evidence_quote": (ext_item.evidence_text[:120] if ext_item and ext_item.evidence_text else ("Scanned image flagged for human review" if is_scanned else "N/A")),
            "evaluation_notes": notes,
        })

# Write CSV
csv_path = "FACT_EXTRACTION_EVALUATION.csv"
fieldnames = [
    "notice_file",
    "evaluation_subset",
    "authority",
    "document_format",
    "notice_category",
    "sha256",
    "field_name",
    "ground_truth_value",
    "extracted_value",
    "match_status",
    "confidence",
    "page_number",
    "evidence_quote",
    "evaluation_notes",
]

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(evaluation_rows)

print(f"Generated {csv_path} with {len(evaluation_rows)} evaluated field rows.")

# Compute subset metrics (excluding authority metadata echo)
def print_subset_metrics(name, subset_rows):
    text_rows = [r for r in subset_rows if r["document_format"] != "SCANNED_PDF" and r["field_name"] != "recruiting_authority"]
    tp = sum(1 for r in text_rows if r["match_status"] == "EXACT_MATCH")
    part = sum(1 for r in text_rows if r["match_status"] == "PARTIAL_MATCH")
    fp_spur = sum(1 for r in text_rows if r["match_status"] == "SPURIOUS_EXTRACTION")
    fp_err = sum(1 for r in text_rows if r["match_status"] == "INCORRECT_VALUE")
    fn = sum(1 for r in text_rows if r["match_status"] == "MISSING_IN_EXTRACTION")
    tn = sum(1 for r in text_rows if r["match_status"] == "NOT_APPLICABLE_IN_NOTICE")
    
    total_eval = len(text_rows)
    gt_present = tp + part + fp_err + fn
    gt_absent = tn + fp_spur
    
    prec = tp / (tp + fp_spur + fp_err) if (tp + fp_spur + fp_err) else 0.0
    rec = tp / gt_present if gt_present else 0.0
    spec = tn / gt_absent if gt_absent else 0.0
    
    print(f"\n=== {name} (Text Extraction Only, Excluding Metadata Echo) ===")
    print(f"  Total Field Instances Evaluated: {total_eval}")
    print(f"  Ground Truth Present: {gt_present} | Ground Truth Absent (N/A): {gt_absent}")
    print(f"  Exact Matches (TP): {tp} | Partial Matches: {part}")
    print(f"  False Positives (Spurious): {fp_spur} | False Positives (Incorrect): {fp_err}")
    print(f"  False Negatives (Missed): {fn} | True Negatives (Correctly Omitted): {tn}")
    print(f"  Precision: {prec*100:.2f}% ({tp}/{tp + fp_spur + fp_err})")
    print(f"  Recall (Exact): {rec*100:.2f}% ({tp}/{gt_present})")
    print(f"  Specificity (Omission Accuracy): {spec*100:.2f}% ({tn}/{gt_absent})")

dev_rows = [r for r in evaluation_rows if r["evaluation_subset"] == "DEVELOPMENT_SET"]
held_rows = [r for r in evaluation_rows if r["evaluation_subset"] == "HELD_OUT_VALIDATION_SET"]

print_subset_metrics("Development Set (16 Notices, 11 Text)", dev_rows)
print_subset_metrics("Held-Out Validation Set (6 Notices, 6 Text)", held_rows)
print_subset_metrics("Combined Text Dataset (17 Text Notices)", evaluation_rows)
