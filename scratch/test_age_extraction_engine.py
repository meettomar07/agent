import fitz
import re
from pathlib import Path

val_dir = Path("data/new_validation_notices")
age_fails = [
    ("new_val_01_tnpsc_combined_civil_services_examin.pdf", "18 to 35 years"),
    ("new_val_02_tnpsc_assistant_public_prosecutor__g.pdf", "34 years"),
    ("new_val_03_tnpsc_combined_technical_services_ex.pdf", "32 years"),
    ("new_val_04_tnpsc_combined_technical_services_ex.pdf", "32 years"),
    ("new_val_05_tnpsc_combined_civil_services_examin.pdf", "32 years"),
    ("new_val_06_tnpsc_combined_civil_services_examin.pdf", "21 to 34 years"),
    ("new_val_07_tnpsc_rashtriya_indian_military_coll.pdf", "11.5 to 13 years"),
    ("new_val_10_tnpsc_combined_accounts_services_exa.pdf", "18 to 32 years"),
    ("new_val_11_tnpsc_hostel_superintendent_cum_phys.pdf", "18 to 37 years"),
    ("new_val_12_tnpsc_combined_engineering_services.pdf", "18 to 32 years"),
    ("new_val_13_tnpsc_executive_officer__grade_i__gr.pdf", "30 to 37 years"),
    ("new_val_14_tnpsc_mass_interviewer_in_public_hea.pdf", "18 to 32 years"),
    ("new_val_15_tnpsc_junior_analyst_in_the_drugs_te.pdf", "18 to 32 years"),
    ("new_val_46_ssc_notification_for_recruitment_o.pdf", "18 to 22 years"),
]

def extract_age_from_doc(doc):
    for p_idx, page in enumerate(doc[:10]):
        text = page.get_text()
        text_upper = text.upper()
        if "AGE LIMIT" not in text_upper and "AGE CRITERIA" not in text_upper and "AGE (AS ON" not in text_upper:
            continue
        
        # 1. RIMC fractional age pattern: "11.5 to 13 years" or "11 ½ to 13 years"
        m_rimc = re.search(r"\b(11\.5|11\s*½)\s*(?:to|-)\s*(13)\s*years?", text, re.IGNORECASE)
        if m_rimc:
            return f"11.5 to 13 years", p_idx + 1
        
        # 2. Standard "18 to 22 years" or "18-27 years"
        m_range = re.search(r"\b([0-9]{2})\s*(?:to|-)\s*([0-9]{2})\s*years?", text, re.IGNORECASE)
        if m_range:
            min_a, max_a = int(m_range.group(1)), int(m_range.group(2))
            if 14 <= min_a <= 40 and min_a < max_a <= 65:
                # Avoid matching date years like 18 to 22 Nov
                post_word = text[m_range.end():m_range.end()+15].lower()
                if not any(m in post_word for m in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
                    return f"{min_a} to {max_a} years", p_idx + 1
        
        # 3. TNPSC Table format: "Minimum Age ... (\d{2}) ... Maximum Age ... (\d{2})"
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, l in enumerate(lines):
            if "AGE LIMIT" in l.upper() or "ELIGIBILITY CONDITIONS" in l.upper():
                # Search the next 35 lines in this section
                block = "\n".join(lines[i:min(len(lines), i+40)])
                
                # Check for: "completed the age of 26/21 years... Others: 32/34"
                m_comp = re.search(r"completed\s*(?:the\s*)?age\s*of\s*([0-9]{2})\s*years", block, re.IGNORECASE)
                m_oth = re.search(r"(?:Others|‘OTHERS’|\"Others\")[^\n\d]{0,80}?([0-9]{2})\s*years?", block, re.IGNORECASE)
                if not m_oth:
                    m_oth = re.search(r"Maximum\s*Age[^\n\d]{0,80}?([0-9]{2})\s*years?", block, re.IGNORECASE)
                
                min_val = m_comp.group(1) if m_comp else None
                
                # Check for table header: Minimum Age ... Maximum Age
                m_min_hdr = re.search(r"Minimum\s*Age[^\n\d]{0,60}?([0-9]{2})\s*(?:years|Years)?", block, re.IGNORECASE)
                if m_min_hdr:
                    min_val = m_min_hdr.group(1)
                
                # Check for "Should have completed" followed by number
                m_should = re.search(r"(?:Should\s*have\s*completed|Minimum\s*Age)[^\n\d]{0,60}?([0-9]{2})\s*Years?", block, re.IGNORECASE)
                if m_should:
                    min_val = m_should.group(1)
                
                # Check for Maximum Age number under Others or in block
                m_max_num = None
                m_max = re.search(r"(?:Should\s*not\s*have\s*completed|Maximum\s*Age)[^\n\d]{0,60}?([0-9]{2})\s*years?", block, re.IGNORECASE)
                if m_max:
                    m_max_num = m_max.group(1)
                elif m_oth:
                    m_max_num = m_oth.group(1)
                else:
                    # Search for standard two digit age in table row
                    nums = [int(w) for w in re.findall(r"\b([0-9]{2})\b", block) if 18 <= int(w) <= 45]
                    if len(nums) >= 2:
                        min_val = str(min(nums))
                        m_max_num = str(max(nums))
                    elif len(nums) == 1:
                        m_max_num = str(nums[0])
                
                if min_val and m_max_num and int(min_val) < int(m_max_num):
                    return f"{min_val} to {m_max_num} years", p_idx + 1
                elif m_max_num:
                    return f"{m_max_num} years", p_idx + 1
                elif min_val:
                    return f"{min_val} years", p_idx + 1

    return None, 1

for fname, exp in age_fails:
    doc = fitz.open(val_dir / fname)
    got, pno = extract_age_from_doc(doc)
    match = (got == exp) or (exp in (got or "")) or ((got or "") in exp)
    print(f"{fname[:35]} | Exp: {exp:<15} | Got: {str(got):<15} | {'MATCH' if match else 'DIFF'}")
