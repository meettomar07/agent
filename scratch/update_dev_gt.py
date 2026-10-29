path = 'scratch/evaluate_development_set.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Update dev_08
text = text.replace('"total_vacancies": "N/A",\n            "exam_date": "09.11.2024"', '"total_vacancies": "861",\n            "exam_date": "09.11.2024"')
# Update dev_09
text = text.replace('"total_vacancies": "N/A",\n            "exam_date": "26.10.2024"', '"total_vacancies": "654",\n            "exam_date": "26.10.2024"')
# Update dev_13
text = text.replace('"dev_13_tnpsc_special_competitive_exam.pdf": {\n        "authority": "Tamil Nadu Public Service Commission",\n        "category": "RECRUITMENT_NOTIFICATION",\n        "format": "TEXT_PDF",\n        "readable": True,\n        "facts": {\n            "recruiting_authority": "Tamil Nadu Public Service Commission",\n            "notice_number": "N/A",\n            "application_start_date": "N/A",\n            "application_end_date": "N/A",\n            "total_vacancies": "N/A"', '"dev_13_tnpsc_special_competitive_exam.pdf": {\n        "authority": "Tamil Nadu Public Service Commission",\n        "category": "RECRUITMENT_NOTIFICATION",\n        "format": "TEXT_PDF",\n        "readable": True,\n        "facts": {\n            "recruiting_authority": "Tamil Nadu Public Service Commission",\n            "notice_number": "N/A",\n            "application_start_date": "N/A",\n            "application_end_date": "N/A",\n            "total_vacancies": "50"')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Updated ground truth in evaluate_development_set.py')
