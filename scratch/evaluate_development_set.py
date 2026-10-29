"""Evaluate extraction accuracy on the independent 13 development notices.
Used for tuning and debugging without touching the frozen 33 held-out validation set.
"""

import csv
import json
from pathlib import Path
import re
import sys
from typing import Dict, Any

from testkart_intelligence.extraction.pdf_extractor import PdfDocumentExtractor
from testkart_intelligence.extraction.html_extractor import HtmlDocumentExtractor
from testkart_intelligence.extraction.fact_extractor import FactExtractor

sys.stdout.reconfigure(encoding='utf-8')

dev_dir = Path("data/development_notices")
pdf_ext = PdfDocumentExtractor()
html_ext = HtmlDocumentExtractor()

# Ground truth for the 13 development set notices
DEV_GROUND_TRUTH = {
    "dev_01_ssc_mts_havaldar_result.pdf": {
        "authority": "Staff Selection Commission",
        "category": "EXAM_RESULT",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Staff Selection Commission",
            "notice_number": "E/15/2025-C-2",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "dev_03_nta_exam_calendar_march_2027.pdf": {
        "authority": "National Testing Agency",
        "category": "EXAM_SCHEDULE",
        "format": "TEXT_PDF",
        "readable": False,  # Scanned image
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
    "dev_04_nta_ugc_net_reexam_admit_card.pdf": {
        "authority": "National Testing Agency",
        "category": "ADMIT_CARD",
        "format": "TEXT_PDF",
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
    "dev_05_nta_nittt_exam_schedule.pdf": {
        "authority": "National Testing Agency",
        "category": "EXAM_SCHEDULE",
        "format": "TEXT_PDF",
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
    "dev_06_nta_aiapget_admit_card.pdf": {
        "authority": "National Testing Agency",
        "category": "ADMIT_CARD",
        "format": "TEXT_PDF",
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
    "dev_07_nta_joint_csir_admit_card.pdf": {
        "authority": "National Testing Agency",
        "category": "ADMIT_CARD",
        "format": "TEXT_PDF",
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
    "dev_08_tnpsc_ctse_diploma_recruitment.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "11/2024",
            "application_start_date": "13.08.2024",
            "application_end_date": "11.09.2024",
            "total_vacancies": "861",
            "exam_date": "09.11.2024",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 32 years",
            "eligibility": "Diploma in Automobile Engineering",
        }
    },
    "dev_09_tnpsc_cts_non_interview_posts.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "9/2024",
            "application_start_date": "26.07.2024",
            "application_end_date": "24.08.2024",
            "total_vacancies": "654",
            "exam_date": "26.10.2024",
            "application_fee": "Rs. 100",
            "age_limit": "N/A",
            "eligibility": "Degree",
        }
    },
    "dev_10_upsc_homoeopathic_physician_notice.html": {
        "authority": "Union Public Service Commission",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "HTML",
        "readable": True,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "04",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "dev_11_upsc_vice_principal_gnctd_notice.html": {
        "authority": "Union Public Service Commission",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "HTML",
        "readable": True,
        "facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "704",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A",
        }
    },
    "dev_12_upsc_manager_sec_officer_result.html": {
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
    "dev_13_tnpsc_special_competitive_exam.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT_NOTIFICATION",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "18 / 2024",
            "application_start_date": "25.11.2024",
            "application_end_date": "24.12.2024",
            "total_vacancies": "50",
            "exam_date": "08.02.2025",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 32 years",
            "eligibility": "Secondary School Leaving Certificate (SSLC)",
        }
    },
    "dev_14_tnpsc_rimc_re_notification.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "EXAMINATION_SCHEDULE",
        "format": "TEXT_PDF",
        "readable": True,
        "facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "10/2024",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "1st Dec 2024",
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
    return re.sub(r"\s+", " ", val.strip()).lower()

def is_match(gt: str, ext: str) -> bool:
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
    # Clean check
    if ngt == next_ or ngt in next_ or next_ in ngt:
        return True
    return False

def evaluate():
    metrics = {f: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for f in EVAL_FIELDS}
    results = []
    
    for filename, doc_meta in DEV_GROUND_TRUTH.items():
        fpath = dev_dir / filename
        bytes_data = fpath.read_bytes()
        is_readable = doc_meta["readable"]
        gt_facts = doc_meta["facts"]
        fmt = doc_meta["format"]
        auth = doc_meta["authority"]
        
        extracted_dict = {}
        if is_readable:
            if fmt == "TEXT_PDF":
                _, pages, _ = pdf_ext.extract(bytes_data)
            else:
                _, pages, _ = html_ext.extract(bytes_data.decode("utf-8", errors="replace"))
            facts_list = FactExtractor.extract_from_pages(
                pages=pages,
                authority_name=auth,
                notice_title=filename,
                official_url=f"https://official.gov.in/{filename}"
            )
            for f in facts_list:
                extracted_dict[f.key] = f.value
        
        for field in EVAL_FIELDS:
            gt_val = gt_facts.get(field, "N/A")
            ext_val = extracted_dict.get(field, "N/A")
            
            if gt_val == "N/A" and ext_val == "N/A":
                match_status = "NOT_APPLICABLE_IN_NOTICE"
                metrics[field]["tn"] += 1
            elif gt_val != "N/A" and ext_val != "N/A":
                if is_match(gt_val, ext_val):
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
            
            results.append({
                "file": filename,
                "field": field,
                "gt": gt_val,
                "ext": ext_val,
                "status": match_status
            })

    print("=" * 80)
    print(f"{'FIELD':<25} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'TN':<4} | {'PRECISION':<10} | {'RECALL':<10} | {'F1':<10}")
    print("=" * 80)
    for field, m in metrics.items():
        tp, fp, fn, tn = m["tp"], m["fp"], m["fn"], m["tn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
        rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
        f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        print(f"{field:<25} | {tp:<4} | {fp:<4} | {fn:<4} | {tn:<4} | {prec*100:8.1f}% | {rec*100:8.1f}% | {f1*100:8.1f}%")
    print("=" * 80)
    
    total_tp = sum(m["tp"] for m in metrics.values())
    total_fp = sum(m["fp"] for m in metrics.values())
    total_fn = sum(m["fn"] for m in metrics.values())
    total_tn = sum(m["tn"] for m in metrics.values())
    overall_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    overall_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = 2 * (overall_prec * overall_rec) / (overall_prec + overall_rec) if (overall_prec + overall_rec) > 0 else 0.0
    omission_acc = total_tn / (total_tn + total_fp) if (total_tn + total_fp) > 0 else 1.0
    print(f"{'OVERALL TOTALS':<25} | {total_tp:<4} | {total_fp:<4} | {total_fn:<4} | {total_tn:<4} | {overall_prec*100:8.1f}% | {overall_rec*100:8.1f}% | {overall_f1*100:8.1f}%")
    print(f"Omission Accuracy: {omission_acc*100:.2f}%")
    
    print("\nNon-matches:")
    for r in results:
        if r["status"] not in ("EXACT_MATCH", "NOT_APPLICABLE_IN_NOTICE"):
            print(f"  [{r['field']}] {r['file']}: GT='{r['gt']}' | EXT='{r['ext']}' | {r['status']}")

if __name__ == "__main__":
    evaluate()
