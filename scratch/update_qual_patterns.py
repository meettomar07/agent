with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''    QUALIFICATION_PATTERNS = [
        r"(?:educational\s*and\s*technical\s*qualification|educational\s*qualification|minimum\s*qualification|essential\s*qualification|prescribed\s*qualification|eligibility\s*criteria)\s*[:\-]?\s*([^.\n]+?(?:Degree|Graduate|Graduation|10\+2|Matriculation|Diploma|Master|B\.E|B\.Tech|Bachelor|Secondary\s*School|SSLC)[^.\n]*)",
        r"(?:educational\s*qualification|essential\s*qualification|minimum\s*qualification|eligibility\s*criteria)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,3}?[^\n\r]*?(Bachelor[']?s\s*Degree[^\.\n]*|Master[']?s\s*Degree[^\.\n]*|Diploma[^\.\n]*|Degree[^\.\n]*|Graduation[^\.\n]*|10\+2[^\.\n]*|Matriculation[^\.\n]*)",
        r"(?:Must\s*possess\s*Minimum\s*General\s*Educational\s*Qualification[^.\n]*)",
        r"(?:posts\s*\(Educational\s*Qualifications-wise\s*viz\.\s*([^.\n\)]+)\))",
    ]'''

replacement = '''    QUALIFICATION_PATTERNS = [
        r"(?:minimum\s+general\s+educational\s+qualification\s+means,?\s*(?:a\s+pass\s+in\s+the\s+)?)(Secondary\s+School\s+Leaving\s+Certificate\s+\(SSLC\)|SSLC)",
        r"(?:educational\s*and\s*technical\s*qualification|educational\s*qualification|minimum\s*qualification|essential\s*qualification|prescribed\s*qualification|eligibility\s*criteria)\s*[:\-]?\s*([^.\n]+?(?:Degree|Graduate|Graduation|10\+2|Matriculation|Diploma|Master|B\.E|B\.Tech|Bachelor|Secondary\s*School|SSLC)[^.\n]*)",
        r"(?:educational\s*qualification|essential\s*qualification|minimum\s*qualification|eligibility\s*criteria)[^\n\r]*[\r\n]+(?:[^\n\r]*[\r\n]+){0,3}?[^\n\r]*?(Bachelor[']?s\s*Degree[^\.\n]*|Master[']?s\s*Degree[^\.\n]*|Diploma[^\.\n]*|Degree[^\.\n]*|Graduation[^\.\n]*|10\+2[^\.\n]*|Matriculation[^\.\n]*)",
        r"(?:Must\s*possess\s*Minimum\s*General\s*Educational\s*Qualification[^.\n]*)",
        r"(?:posts\s*\(Educational\s*Qualifications-wise\s*viz\.\s*([^.\n\)]+)\))",
    ]'''

if "QUALIFICATION_PATTERNS = [" in text:
    idx = text.find("    QUALIFICATION_PATTERNS = [")
    end_idx = text.find("    ADVT_PATTERNS = [", idx)
    text = text[:idx] + replacement + "\n\n" + text[end_idx:]
    with open('testkart_intelligence/extraction/fact_extractor.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Successfully updated QUALIFICATION_PATTERNS in fact_extractor.py")
else:
    print("Could not find QUALIFICATION_PATTERNS in file")
