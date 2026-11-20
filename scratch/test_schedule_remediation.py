import re
from testkart_intelligence.extraction.date_normalizer import DateNormalizer

text = """
1.  Junior Engineer Examination, 2026  Paper-I  (CBE) : 02nd to  06th November, 2026
2.  Sub-Inspector in Delhi Police and  Central  Armed  Police  Forces  Examination, 2026. : CBE  20th to  28th November, 2026
3.  Combined Higher Secondary (10+2)  Level Examination, 2026 : Tier-I  (CBE) : 30th November, to  31st December, 2026
"""

def extract_dates_from_schedule_val(val_text: str):
    # 1. Day-to-day same month range: 02nd to 06th November, 2026
    m_day_range = re.search(
        r"([0-9]{1,2}(?:st|nd|rd|th)?)\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?)\s+([A-Za-z]+),?\s+([0-9]{4})",
        val_text, re.IGNORECASE
    )
    if m_day_range:
        d1, d2, month, year = m_day_range.groups()
        s1 = f"{d1} {month} {year}"
        s2 = f"{d2} {month} {year}"
        c1 = DateNormalizer.normalize_single_date(s1) or s1
        c2 = DateNormalizer.normalize_single_date(s2) or s2
        return f"{c1} to {c2}", f"{s1} to {s2}"

    # 2. Month-to-month range: 30th November, to 31st December, 2026
    m_month_range = re.search(
        r"([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+),?\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+),?\s+([0-9]{4})",
        val_text, re.IGNORECASE
    )
    if m_month_range:
        d1_m, d2_m, year = m_month_range.groups()
        s1 = f"{d1_m} {year}"
        s2 = f"{d2_m} {year}"
        c1 = DateNormalizer.normalize_single_date(s1) or s1
        c2 = DateNormalizer.normalize_single_date(s2) or s2
        return f"{c1} to {c2}", f"{s1} to {s2}"

    # 3. Standard range
    range_pat = r"([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4})"
    m_std = re.search(range_pat, val_text, re.IGNORECASE)
    if m_std:
        s1 = m_std.group(1).strip()
        s2 = m_std.group(2).strip()
        c1 = DateNormalizer.normalize_single_date(s1) or s1
        c2 = DateNormalizer.normalize_single_date(s2) or s2
        return f"{c1} to {c2}", f"{s1} to {s2}"

    # 4. Single date
    single_date_pat = r"([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4})"
    m_s = re.search(single_date_pat, val_text, re.IGNORECASE)
    if m_s:
        s = m_s.group(1).strip()
        c = DateNormalizer.normalize_single_date(s) or s
        return c, s

    return None, None

for line in text.strip().splitlines():
    parts = line.split(" : ")
    label = parts[0]
    val = parts[-1]
    norm, raw = extract_dates_from_schedule_val(val)
    print(f"Label: {label[:30]} | Extracted: {raw} -> {norm}")
