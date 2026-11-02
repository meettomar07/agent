from pathlib import Path

path = Path("testkart_intelligence/extraction/fact_extractor.py")
content = path.read_text(encoding="utf-8")

# 1. Update line 75 in END_DATE_PATTERNS
old_p = r'r"last\s*date[^\n:]{0,90}?(?:submission|receipt|apply|application|fee)[^\n:]{0,40}[:\-–]\s*([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})"'
new_p = r'r"last\s*date[^\n:]{0,90}?(?:submission|receipt|apply|application|fee)[^\n:]{0,60}?(?:\s*is\s*|[:\-–]\s*)([0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})"'

assert old_p in content, "Failed to find old_p"
content = content.replace(old_p, new_p)

# 2. Update is_result_or_key check
old_res = """        is_result_or_key = any(
            k in title_lower or k in first_page_text
            for k in [
                "written result", "final result", "declaration of result",
                "marks write-up", "shortlist", "answer key", "admit card",
                "hall ticket", "cancellation", "withdrawal"
            ]
        )"""

new_res = """        is_result_or_key = any(
            k in title_lower or (k in first_page_text and k not in ("admit card", "hall ticket"))
            for k in [
                "written result", "final result", "declaration of result",
                "marks write-up", "shortlist", "answer key", "admit card",
                "hall ticket", "cancellation", "withdrawal"
            ]
        )"""

assert old_res in content, "Failed to find old_res"
content = content.replace(old_res, new_res)

path.write_text(content, encoding="utf-8")
print("Updated fact_extractor.py successfully!")
