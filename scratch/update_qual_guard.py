from pathlib import Path

fe_path = Path("testkart_intelligence/extraction/fact_extractor.py")
fe_text = fe_path.read_text(encoding="utf-8")

# 1. Check extracted_keys for eligibility
old_qual_check = """        # Look for Educational Qualification / Eligibility
        qual_found = False
        if not is_result_or_key:"""

new_qual_check = """        # Look for Educational Qualification / Eligibility
        qual_found = "eligibility" in extracted_keys
        if not is_result_or_key and not qual_found:"""

# 2. Also guard against "higher than the" in candidate qualification
old_guard = """                        if any(b in val_str.lower() for b in ["order of studies", "order of study", "pattern of study", "in the order of", "degree : institution : class"]):
                            continue"""

new_guard = """                        if any(b in val_str.lower() for b in ["order of studies", "order of study", "pattern of study", "in the order of", "degree : institution : class", "higher than the"]):
                            continue"""

if old_qual_check in fe_text:
    fe_text = fe_text.replace(old_qual_check, new_qual_check)
    print("Updated qual_found to check extracted_keys.")

if old_guard in fe_text:
    fe_text = fe_text.replace(old_guard, new_guard)
    print("Updated qualification guard with 'higher than the'.")

fe_path.write_text(fe_text, encoding="utf-8")
