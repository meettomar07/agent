import fitz
import re
from testkart_intelligence.extraction.date_normalizer import DateNormalizer

doc = fitz.open("data/new_validation_notices/new_val_12_tnpsc_combined_engineering_services.pdf")
page_text = doc[3].get_text() # Page 4

def parse_schedule_from_text_block(text: str):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    single_date_pat = r"^([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4})"
    
    extracted = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        line_l = line.lower()
        
        # 1. Date of Notification
        if any(k in line_l for k in ["date of notification", "date of publication", "advt date"]):
            if "publication_date" not in extracted:
                for k in range(1, 4):
                    if i + k < len(lines):
                        m = re.search(single_date_pat, lines[i+k])
                        if m:
                            extracted["publication_date"] = (m.group(1), f"{line}: {lines[i+k]}")
                            break
        
        # 2. Last date for submission
        elif any(k in line_l for k in ["last date for submission", "closing date", "last date to apply"]):
            if "application_end_date" not in extracted:
                for k in range(1, 4):
                    if i + k < len(lines):
                        m = re.search(single_date_pat, lines[i+k])
                        if m:
                            extracted["application_end_date"] = (m.group(1), f"{line}: {lines[i+k]}")
                            break
        
        # 3. Date of examination / Paper-I / CBT
        elif any(k in line_l for k in ["date of written examination", "date of examination", "schedule of cbt", "date and time of examination"]):
            if "exam_date" not in extracted:
                for k in range(1, 8):
                    if i + k < len(lines):
                        m = re.search(single_date_pat, lines[i+k])
                        if m:
                            extracted["exam_date"] = (m.group(1), f"{line} ... {lines[i+k]}")
                            break
        
        i += 1
    return extracted

res = parse_schedule_from_text_block(page_text)
print("Extracted from new_val_12 Page 4:")
for k, v in res.items():
    print(f"  {k}: {v[0]} (evidence: {v[1]})")
