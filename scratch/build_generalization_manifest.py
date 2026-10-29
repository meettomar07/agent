import json
from pathlib import Path
import hashlib

data_dir = Path("data/generalization_notices")
with open("scratch/harvested_generalization_candidates.json", "r", encoding="utf-8") as f:
    items = json.load(f)

# Ground truth dictionary keyed by filename
gt_facts = {
    "gen_01_tnpsc_assistant_jailor__men___women.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "09/2023",
            "application_start_date": "12.04.2023",
            "application_end_date": "11.05.2023",
            "total_vacancies": "59",
            "exam_date": "01.07.2023",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 32 years",
            "eligibility": "degree of any of the Universities recognized by the University Grants Commission"
        }
    },
    "gen_02_tnpsc_tourist_officer.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "03/2023",
            "application_start_date": "25.01.2023",
            "application_end_date": "23.02.2023",
            "total_vacancies": "3",
            "exam_date": "10.06.2023",
            "application_fee": "Rs. 200",
            "age_limit": "18 to 32 years",
            "eligibility": "Post Graduate degree in Travel and Tourism"
        }
    },
    "gen_03_tnpsc_road_inspector_in_rural_develo.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "02/2023",
            "application_start_date": "13.01.2023",
            "application_end_date": "11.02.2023",
            "total_vacancies": "761",
            "exam_date": "07.05.2023",
            "application_fee": "Rs. 100",
            "age_limit": "37 years",
            "eligibility": "I.T.I. Certificate in Civil Draughtsmenship"
        }
    },
    "gen_04_tnpsc_junior_scientific_officer.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "10/2023",
            "application_start_date": "27.04.2023",
            "application_end_date": "26.05.2023",
            "total_vacancies": "31",
            "exam_date": "23.07.2023",
            "application_fee": "Rs. 100",
            "age_limit": "32 years",
            "eligibility": "M.Sc., (Forensic Science) Degree"
        }
    },
    "gen_05_tnpsc_combined_geology_subordinate_s.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "11/2023",
            "application_start_date": "25.05.2023",
            "application_end_date": "23.06.2023",
            "total_vacancies": "40",
            "exam_date": "18.08.2023",
            "application_fee": "Rs. 100",
            "age_limit": "32 years",
            "eligibility": "Master of Science degree in Geology"
        }
    },
    "gen_06_tnpsc_civil_judge_in_tamil_nadu_stat.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "12/2023",
            "application_start_date": "01.06.2023",
            "application_end_date": "30.06.2023",
            "total_vacancies": "245",
            "exam_date": "19.08.2023",
            "application_fee": "Rs. 100",
            "age_limit": "25 to 37 years",
            "eligibility": "Degree in Law of a University in India"
        }
    },
    "gen_07_tnpsc_combined_research_assistant_in.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "13/2023",
            "application_start_date": "26.06.2023",
            "application_end_date": "25.07.2023",
            "total_vacancies": "6",
            "exam_date": "09.09.2023",
            "application_fee": "Rs. 100",
            "age_limit": "18 to 32 years",
            "eligibility": "Master's Degree of any recognized University or Institution with Statistics"
        }
    },
    "gen_08_tnpsc_assistant_training_officer___j.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "14/2023",
            "application_start_date": "18.07.2023",
            "application_end_date": "16.08.2023",
            "total_vacancies": "7",
            "exam_date": "05.10.2023",
            "application_fee": "Rs. 100",
            "age_limit": "37 years",
            "eligibility": "Must have been declared eligible for College course of study"
        }
    },
    "gen_09_tnpsc_combined_library_examination.pdf": {
        "authority": "Tamil Nadu Public Service Commission",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Tamil Nadu Public Service Commission",
            "notice_number": "04/2023",
            "application_start_date": "31.01.2023",
            "application_end_date": "01.03.2023",
            "total_vacancies": "35",
            "exam_date": "13.05.2023",
            "application_fee": "Rs. 100",
            "age_limit": "32 years",
            "eligibility": "Master's Degree in Library Science or Information Science"
        }
    },
    "gen_10_nta_advertisement_for_video_editor.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT",
        "format": "SCANNED_PDF",
        "readable": False,
        "ground_truth_facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "53",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A"
        }
    },
    "gen_11_nta_engagement_of_general_manager.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "1",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "below 58 years",
            "eligibility": "Ph.D. in Psychometrics, Educational Measurement, Statistics"
        }
    },
    "gen_12_nta_engagement_of_general_manager.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "1",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "below 55 years",
            "eligibility": "B.Tech/B.E./M.Tech/M.S. in Computer Science"
        }
    },
    "gen_13_nta_engagement_of_general_manager.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "1",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "below 55 years",
            "eligibility": "Master's degree/B.Tech/MBA"
        }
    },
    "gen_14_nta_engagement_of_general_manager.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "1",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "below 60 years",
            "eligibility": "Master's degree"
        }
    },
    "gen_15_nta_engagement_of_young_profession.pdf": {
        "authority": "National Testing Agency",
        "category": "RECRUITMENT",
        "format": "TEXT_PDF",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "16",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "Civil Services Examination"
        }
    },
    "gen_16_nta_inviting_online_application_fo.pdf": {
        "authority": "National Testing Agency",
        "category": "ADMISSION",
        "format": "SCANNED_PDF",
        "readable": False,
        "ground_truth_facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A"
        }
    },
    "gen_17_nta_correction_in_application_form.pdf": {
        "authority": "National Testing Agency",
        "category": "CORRIGENDUM",
        "format": "SCANNED_PDF",
        "readable": False,
        "ground_truth_facts": {
            "recruiting_authority": "National Testing Agency",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A"
        }
    },
    "gen_18_upsc_04_posts_of_homoeopathic_physi.html": {
        "authority": "Union Public Service Commission",
        "category": "RECRUITMENT",
        "format": "HTML",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "4",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A"
        }
    },
    "gen_19_upsc_704_posts_of_vice_principal_in.html": {
        "authority": "Union Public Service Commission",
        "category": "RECRUITMENT",
        "format": "HTML",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "704",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A"
        }
    },
    "gen_20_upsc_combined_geo_scientist_prelimi.html": {
        "authority": "Union Public Service Commission",
        "category": "EXAM_DATE",
        "format": "HTML",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A"
        }
    },
    "gen_21_upsc_indian_economic_service_interv.html": {
        "authority": "Union Public Service Commission",
        "category": "INTERVIEW_SCHEDULE",
        "format": "HTML",
        "readable": True,
        "ground_truth_facts": {
            "recruiting_authority": "Union Public Service Commission",
            "notice_number": "N/A",
            "application_start_date": "N/A",
            "application_end_date": "N/A",
            "total_vacancies": "N/A",
            "exam_date": "N/A",
            "application_fee": "N/A",
            "age_limit": "N/A",
            "eligibility": "N/A"
        }
    }
}

manifest = {
    "dataset_name": "INDEPENDENT_GENERALIZATION_DATASET",
    "created_at": "2026-10-29T12:00:00Z",
    "status": "FROZEN_FOR_INDEPENDENT_GENERALIZATION_TEST",
    "total_documents": len(items),
    "authorities_distribution": {
        "Tamil Nadu Public Service Commission": 9,
        "National Testing Agency": 8,
        "Union Public Service Commission": 4
    },
    "format_distribution": {
        "TEXT_PDF": 14,
        "SCANNED_PDF": 3,
        "HTML": 4
    },
    "documents": {}
}

for item in items:
    fname = item["filename"]
    fpath = data_dir / fname
    with open(fpath, "rb") as f:
        content = f.read()
    h = hashlib.sha256(content).hexdigest()
    
    gt = gt_facts[fname]
    manifest["documents"][fname] = {
        "sha256": h,
        "size_bytes": len(content),
        "authority": gt["authority"],
        "category": gt["category"],
        "format": gt["format"],
        "readable": gt["readable"],
        "ground_truth_facts": gt["ground_truth_facts"]
    }

manifest_path = Path("GENERALIZATION_SET_MANIFEST.json")
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Created {manifest_path} with {len(manifest['documents'])} documents.")
