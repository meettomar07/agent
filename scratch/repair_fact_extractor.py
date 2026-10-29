# Let's fix QUALIFICATION_PATTERNS properly using raw triple-quoted strings or clean escaping

with open('testkart_intelligence/extraction/fact_extractor.py', 'r', encoding='utf-8') as f:
    content = f.read()

qual_start = content.find("    QUALIFICATION_PATTERNS = [")
advt_start = content.find("    ADVT_PATTERNS = [")

clean_block = '''    QUALIFICATION_PATTERNS = [
        r"(?:minimum\\s+general\\s+educational\\s+qualification\\s+means,?\\s*(?:a\\s+pass\\s+in\\s+the\\s+)?)(Secondary\\s+School\\s+Leaving\\s+Certificate\\s+\\(SSLC\\)|SSLC)",
        r"(?:educational\\s*and\\s*technical\\s*qualification|educational\\s*qualification|minimum\\s*qualification|essential\\s*qualification|prescribed\\s*qualification|eligibility\\s*criteria)\\s*[:\\-]?\\s*([^.\\n]+?(?:Degree|Graduate|Graduation|10\\+2|Matriculation|Diploma|Master|B\\.E|B\\.Tech|Bachelor|Secondary\\s*School|SSLC)[^.\\n]*)",
        r"(?:educational\\s*qualification|essential\\s*qualification|minimum\\s*qualification|eligibility\\s*criteria)[^\\n\\r]*[\\r\\n]+(?:[^\\n\\r]*[\\r\\n]+){0,3}?[^\\n\\r]*?(Bachelor[']?s\\s*Degree[^\\.\\n]*|Master[']?s\\s*Degree[^\\.\\n]*|Diploma[^\\.\\n]*|Degree[^\\.\\n]*|Graduation[^\\.\\n]*|10\\+2[^\\.\\n]*|Matriculation[^\\.\\n]*)",
        r"(?:Must\\s*possess\\s*Minimum\\s*General\\s*Educational\\s*Qualification[^.\\n]*)",
        r"(?:posts\\s*\\(Educational\\s*Qualifications-wise\\s*viz\\.\\s*([^.\\n\\)]+)\\))",
    ]'''

new_content = content[:qual_start] + clean_block + "\n\n" + content[advt_start:]

with open('testkart_intelligence/extraction/fact_extractor.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Repaired fact_extractor.py successfully")
