import re
from pathlib import Path

path = Path("testkart_intelligence/extraction/fact_extractor.py")
content = path.read_text(encoding="utf-8")

# 1. VACANCY_PATTERNS
old_vac = """    VACANCY_PATTERNS = [
        r"(?:total\\s*(?:number|no\\.?)?\\s*of\\s*vacancies|number\\s*of\\s*posts|total\\s*posts|tentative\\s*vacancies)\\s*[:\\-–]?\\s*([0-9,]+)",
        r"(?:total\\s*no\\.\\s*of\\s*vacancies.*?is\\s*)([0-9,]+)",
        r"(?:vacancies.*?expected\\s*to\\s*be\\s*(?:approximately\\s*)?|approximately\\s*)([0-9,]+)\\s*(?:vacancies|posts)",
        r"([0-9,]+)\\s*(?:vacancies|posts)\\s*(?:are\\s*available|to\\s*be\\s*filled|tentative)",
        r"(?:vacancies|posts)\\s*[:\\-–]\\s*([0-9,]+)",
        r"(?:Total|Grand\\s*Total)\\s*(?:number\\s*of\\s*)?(?:vacancies|posts)\\s*[:\\-–]?\\s*([0-9,]+)",
        r"(?:number\\s*of\\s*vacancies.*?is\\s*(?:at\\s*present\\s*)?)([0-9,]+)",
        r"(?:Number\\s*of\\s*vacancies[^\\n:\\d]{0,40}[:\\|\\-]\\s*)([0-9,]+)",
        r"\\b(\\d{1,4})\\s+posts?\\s+of\\b",
    ]"""

new_vac = """    VACANCY_PATTERNS = [
        r"(?:total\\s*(?:number|no\\.?)?\\s*of\\s*vacancies|number\\s*of\\s*posts|total\\s*posts|tentative\\s*vacancies)\\s*[:\\-–]?\\s*([0-9,]+)",
        r"(?:total\\s*no\\.\\s*of\\s*vacancies.*?is\\s*)([0-9,]+)",
        r"(?:total\\s*vacancies\\s*(?:are\\s*)?(?:revised|enhanced|increased)\\s*from\\s*[0-9,]+\\s*to\\s*)([0-9,]+)",
        r"(?:total\\s*vacancies\\s*(?:are\\s*)?(?:revised|enhanced|increased)\\s*to\\s*)([0-9,]+)",
        r"(?:vacancies\\s*(?:are\\s*)?enhanced\\s*from\\s*[0-9,]+\\s*to\\s*)([0-9,]+)",
        r"(?:vacancies.*?expected\\s*to\\s*be\\s*(?:approximately\\s*)?|approximately\\s*)([0-9,]+)\\s*(?:vacancies|posts)",
        r"([0-9,]+)\\s*(?:vacancies|posts)\\s*(?:are\\s*available|to\\s*be\\s*filled|tentative)",
        r"(?:vacancies|posts)\\s*[:\\-–]\\s*([0-9,]+)",
        r"(?:Total|Grand\\s*Total)\\s*(?:number\\s*of\\s*)?(?:vacancies|posts)\\s*[:\\-–]?\\s*([0-9,]+)",
        r"(?:number\\s*of\\s*vacancies.*?is\\s*(?:at\\s*present\\s*)?)([0-9,]+)",
        r"(?:Number\\s*of\\s*vacancies[^\\n:\\d]{0,40}[:\\|\\-]\\s*)([0-9,]+)",
        r"\\b(\\d{1,4})\\s+posts?\\s+of\\b",
    ]"""

# 2. RANGE_DATE_PATTERNS
old_range = """    RANGE_DATE_PATTERNS = [
        r"(?:dates?\\s*for\\s*(?:submission\\s*of\\s*)?online\\s*applications?|online\\s*submission\\s*of\\s*application\\s*form[^\\n:]*|online\\s*application\\s*window|application\\s*window)\\s*[:\\-–]?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-\\s]+[0-9]{1,2}[\\/\\.\\-\\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})\\s*(?:to|-)\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-\\s]+[0-9]{1,2}[\\/\\.\\-\\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
    ]"""

new_range = """    RANGE_DATE_PATTERNS = [
        r"(?:dates?\\s*for\\s*(?:submission\\s*of\\s*)?online\\s*applications?|online\\s*submission\\s*of\\s*application\\s*form[^\\n:]*|online\\s*application\\s*window|application\\s*window)\\s*[:\\-–]?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-\\s]+[0-9]{1,2}[\\/\\.\\-\\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})\\s*(?:to|-)\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-\\s]+[0-9]{1,2}[\\/\\.\\-\\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"(?:applications?\\s*(?:are\\s*)?invited\\s*(?:online\\s*)?from\\s*)([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})\\s*(?:to|-)\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
    ]"""

# 3. START_DATE_PATTERNS
old_start = """    START_DATE_PATTERNS = [
        r"(?:opening\\s*date|start\\s*date|date\\s*of\\s*commencement(?:\\s*of\\s*on-?line\\s*application)?|date\\s*of\\s*notification|application\\s*starts|online\\s*registration\\s*from|submission\\s*of\\s*online\\s*application\\s*starts?)\\s*[:\\-–]?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"(?:opening\\s*date|start\\s*date|date\\s*of\\s*commencement|date\\s*of\\s*notification)\\s*[\\r\\n]+\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
    ]"""

new_start = """    START_DATE_PATTERNS = [
        r"(?:opening\\s*date[^\\n:]{0,50}?|start\\s*date|date\\s*of\\s*commencement(?:\\s*of\\s*on-?line\\s*application)?|date\\s*of\\s*notification|application\\s*starts|online\\s*registration\\s*from|submission\\s*of\\s*online\\s*application\\s*starts?)\\s*[:\\-–]?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"(?:opening\\s*date|start\\s*date|date\\s*of\\s*commencement|date\\s*of\\s*notification)\\s*[\\r\\n]+\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
    ]"""

# 4. END_DATE_PATTERNS
old_end = """    END_DATE_PATTERNS = [
        r"(?:closing\\s*date|last\\s*date(?:\\s*(?:and\\s*time)?\\s*for\\s*(?:submission|receipt|apply|applying|payment))?(?:\\s*of\\s*(?:examination\\s*fee|on-?line\\s*application|applications?))?|application\\s*ends)\\s*[:\\-–]?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"(?:applications?\\s*(?:can\\s*be\\s*filled|to\\s*be\\s*submitted)\\s*up\\s*to|last\\s*date\\s*for\\s*receipt\\s*of\\s*applications?)\\s*[:\\-–]?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"(?:closing\\s*date|last\\s*date(?:\\s*and\\s*time\\s*for\\s*submission\\s*of\\s*online\\s*application)?)\\s*[\\r\\n]+\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"last\\s*date[^\\n:]{0,90}?(?:submission|receipt|apply|application|fee)[^\\n:]{0,40}[:\\-–]\\s*([0-9]{1,2}[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
    ]"""

new_end = """    END_DATE_PATTERNS = [
        r"(?:(?:last|closing)\\s*date[^\\n:]{0,60}?(?:extended|rescheduled)\\s*(?:up\\s*)?to\\s*)([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"(?:closing\\s*date[^\\n:]{0,50}?|last\\s*date(?:\\s*(?:and\\s*time)?\\s*for\\s*(?:submission|receipt|apply|applying|payment))?(?:\\s*of\\s*(?:examination\\s*fee|on-?line\\s*application|applications?))?|application\\s*ends)\\s*(?:is\\s*|[:\\-–]\\s*)([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"(?:applications?\\s*(?:can\\s*be\\s*filled|to\\s*be\\s*submitted)\\s*up\\s*to|last\\s*date\\s*for\\s*receipt\\s*of\\s*applications?)\\s*[:\\-–]?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"(?:closing\\s*date|last\\s*date(?:\\s*and\\s*time\\s*for\\s*submission\\s*of\\s*online\\s*application)?)\\s*[\\r\\n]+\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"last\\s*date[^\\n:]{0,90}?(?:submission|receipt|apply|application|fee)[^\\n:]{0,40}[:\\-–]\\s*([0-9]{1,2}[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
    ]"""

# 5. EXAM_DATE_PATTERNS
old_exam = """    EXAM_DATE_PATTERNS = [
        r"(?:Date\\s*(?:and\\s*Time\\s*)?of\\s*(?:[A-Za-z\\(\\)\\/\\s]{0,40})?Examination|Examination\\s*Schedule|Schedule\\s*of\\s*Examination)[^\\n\\r]*[\\r\\n]+(?:[^\\n\\r]*[\\r\\n]+){0,10}?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
        r"(?:date\\s*(?:and\\s*time\\s*)?of\\s*(?:entrance\\s*|preliminary\\s*)?examination|examination\\s*date|exam\\s*date|schedule\\s*of\\s*(?:tier[- ]?[a-zA-Z0-9]+\\s*)?(?:\\([^\\)]+\\)\\s*)?(?:examination)?|cbt\\s*date|schedule\\s*of\\s*cbt)\\s*[:\\-–]?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}(?:\\s*(?:to|-)\\s*[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})?|(?:[A-Za-z]+[- ][A-Za-z]+,?\\s+[0-9]{4})|(?:[A-Za-z]+\\s+[0-9]{4})|(?:(?:[0-9]{1,2}[,\\s]+)+(?:and\\s+)?[0-9]{1,2}\\s+[A-Za-z]+\\s+[0-9]{4}))",
        r"(?:examination|cbt|test)\\s*(?:is\\s*)?(?:(?:scheduled\\s*)?to\\s*be\\s*held|conducted.*?from|held)\\s*(?:on|from)\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})\\s*(?:(?:to|-)\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}))?",
        r"(?:Date\\s*and\\s*Time\\s*of\\s*Examination|Examination\\s*Schedule)[^\\n\\r]*[\\r\\n]+(?:[^\\n\\r]*[\\r\\n]+){1,6}?\\s*([0-9]{1,2}[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4})",
    ]"""

new_exam = """    EXAM_DATE_PATTERNS = [
        # 1. Header or Label followed by colon or dash
        r"(?:Dates?\\s*(?:and\\s*Time\\s*)?of\\s*(?:[A-Za-z\\(\\)\\/\\s]{0,40})?Examination|Revised\\s*(?:examination\\s*)?schedule|Schedule\\s*of\\s*(?:Computer\\s*Based\\s*)?(?:[A-Za-z0-9\\(\\)\\/\\s\\-]{0,40})?Examination|Examination\\s*Schedule|Time\\s*Table|Schedule\\s*of\\s*CBT|CBT\\s*Date|Date\\s*of\\s*Screening\\s*Examination)\\s*[:\\-–]?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+(?:to|-)\\s+[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}(?:\\s*(?:to|-)\\s*[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})?|(?:[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}\\s+and\\s+[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})|(?:(?:[0-9]{1,2}(?:st|nd|rd|th)?[,\\s]+)+(?:and\\s+)?[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})|(?:[A-Za-z]+,?\\s+[0-9]{4})|(?:[A-Za-z]+[- ][A-Za-z]+,?\\s+[0-9]{4}))",
        # 2. Prose sentence: "The Examination will be held on ...", "is scheduled to be held on ...", "conducted from ..."
        r"(?:The\\s+)?(?:Examination|CBT|Test|Screening\\s+test)\\s*(?:will\\s*be\\s*held\\s*on|is\\s*(?:scheduled\\s*)?to\\s*be\\s*held\\s*on|to\\s*be\\s*conducted\\s*on|conducted\\s*from|commencing\\s*from|held\\s*on)\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+(?:to|-)\\s+[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}(?:\\s*(?:to|-)\\s*[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})?|(?:[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}\\s+and\\s+[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})|(?:(?:[0-9]{1,2}(?:st|nd|rd|th)?[,\\s]+)+(?:and\\s+)?[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})|(?:[A-Za-z]+,?\\s+[0-9]{4}))",
        # 3. Multiline header: "Date of Examination ... \\n 15.03.2027"
        r"(?:Dates?\\s*(?:and\\s*Time\\s*)?of\\s*(?:[A-Za-z\\(\\)\\/\\s]{0,40})?Examination|Examination\\s*Schedule|Schedule\\s*of\\s*Examination|Schedule\\s*of\\s*CBT)[^\\n\\r]*[\\r\\n]+(?:[^\\n\\r]*[\\r\\n]+){0,10}?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+(?:to|-)\\s+[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4}|(?:[A-Za-z]+,?\\s+[0-9]{4}))",
        # 4. Standard fallback for simple "examination date: DD/MM/YYYY"
        r"(?:examination\\s*date|exam\\s*date)\\s*[:\\-–]?\\s*([0-9]{1,2}[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",
    ]"""

# 6. AGE_PATTERNS
old_age_pat = """        r"(?:not\\s*exceeding\\s*([0-9]{2})\\s*years(?:\\s*as\\s*on\\s*[^\\.\\n]+)?)\","""
new_age_pat = """        r"(?:not\\s*exceeding\\s*([0-9]{2}\\s*years(?:\\s*as\\s*on\\s*[^\\.\\n]+)?))",
        r"(?:age\\s*limit\\s*[:\\-–]\\s*)(Not\\s*exceeding\\s*[0-9]{2}\\s*years[^\\.\\n]*)","""

# 7. QUALIFICATION_PATTERNS
old_qual = """    QUALIFICATION_PATTERNS = [
        r"(?:minimum\\s+general\\s+educational\\s+qualification\\s+means,?\\s*(?:a\\s+pass\\s+in\\s+the\\s+)?)(Secondary\\s+School\\s+Leaving\\s+Certificate\\s+\\(SSLC\\)|SSLC)",
        r"(?:educational\\s*and\\s*technical\\s*qualification|educational\\s*qualification|minimum\\s*qualification|essential\\s*qualification|prescribed\\s*qualification|eligibility\\s*criteria)\\s*[:\\-]?\\s*([^.\\n]+?(?:Degree|Graduate|Graduation|10\\+2|Matriculation|Diploma|Master|B\\.E|B\\.Tech|Bachelor|Secondary\\s*School|SSLC)[^.\\n]*)",
        r"(?:educational\\s*qualification|essential\\s*qualification|minimum\\s*qualification|eligibility\\s*criteria)[^\\n\\r]*[\\r\\n]+(?:[^\\n\\r]*[\\r\\n]+){0,3}?[^\\n\\r]*?(Bachelor[']?s\\s*Degree[^\\.\\n]*|Master[']?s\\s*Degree[^\\.\\n]*|Diploma[^\\.\\n]*|Degree[^\\.\\n]*|Graduation[^\\.\\n]*|10\\+2[^\\.\\n]*|Matriculation[^\\.\\n]*)",
        r"(?:Must\\s*possess\\s*Minimum\\s*General\\s*Educational\\s*Qualification[^.\\n]*)",
        r"(?:posts\\s*\\(Educational\\s*Qualifications-wise\\s*viz\\.\\s*([^.\\n\\)]+)\\))",
    ]"""

new_qual = """    QUALIFICATION_PATTERNS = [
        # Explicit Qualifications: or Eligibility: line header
        r"(?:Qualifications?|Eligibility)\\s*[:\\-–]\\s*([^\\n\\r]+)",
        # SSLC
        r"(?:minimum\\s+general\\s+educational\\s+qualification\\s+means,?\\s*(?:a\\s+pass\\s+in\\s+the\\s+)?)(Secondary\\s+School\\s+Leaving\\s+Certificate\\s+\\(SSLC\\)|SSLC)",
        # Educational qualification followed by details
        r"(?:educational\\s*and\\s*technical\\s*qualification|educational\\s*qualification|minimum\\s*qualification|essential\\s*qualification|prescribed\\s*qualification|eligibility\\s*criteria)\\s*(?:is\\s*(?:amended|modified)\\s*as\\s*(?:under)?\\s*)?[:\\-–]?\\s*([^.\\n]+?(?:Degree|Graduate|Graduation|10\\+2|12th|Matriculation|Diploma|Master|B\\.E|B\\.Tech|Bachelor|Secondary\\s*School|SSLC|MBBS|Law|LLB|Ayurvedic|Unani|MD|MS|DNB|enrolled\\s*in)[^.\\n]*)",
        # Multiline qualification
        r"(?:educational\\s*qualification|essential\\s*qualification|minimum\\s*qualification|eligibility\\s*criteria)[^\\n\\r]*[\\r\\n]+(?:[^\\n\\r]*[\\r\\n]+){0,3}?[^\\n\\r]*?(Bachelor[']?s\\s*Degree[^\\.\\n]*|Master[']?s\\s*Degree[^\\.\\n]*|Diploma[^\\.\\n]*|Degree[^\\.\\n]*|Graduation[^\\.\\n]*|10\\+2[^\\.\\n]*|12th[^\\.\\n]*|Matriculation[^\\.\\n]*|MBBS[^\\.\\n]*|Law[^\\.\\n]*)",
        # Standalone "Must possess..."
        r"(?:Must\\s*possess\\s*(?:a\\s*)?(?:Bachelor[']?s\\s*Degree|Master[']?s\\s*Degree|Degree|Diploma|Minimum\\s*General\\s*Educational\\s*Qualification)[^.\\n]*)",
        # Departmental circular condition
        r"(?:Only\\s+departmental\\s+candidates\\s+serving\\s+regularly[^.\\n]*)",
        r"(?:posts\\s*\\(Educational\\s*Qualifications-wise\\s*viz\\.\\s*([^.\\n\\)]+)\\))",
    ]"""

# Normalize content to \n for replacement
norm_content = content.replace("\r\n", "\n")

replacements = [
    (old_vac, new_vac, "VACANCY_PATTERNS"),
    (old_range, new_range, "RANGE_DATE_PATTERNS"),
    (old_start, new_start, "START_DATE_PATTERNS"),
    (old_end, new_end, "END_DATE_PATTERNS"),
    (old_exam, new_exam, "EXAM_DATE_PATTERNS"),
    (old_age_pat, new_age_pat, "AGE_PATTERNS"),
    (old_qual, new_qual, "QUALIFICATION_PATTERNS"),
]

for old, new, label in replacements:
    assert old in norm_content, f"Failed to find {label}"
    norm_content = norm_content.replace(old, new)
    print(f"Replaced {label}")

# Also check clean qualification method so that preamble stripping does not truncate degrees
# Write back with original CRLF or LF (both valid Python)
path.write_text(norm_content, encoding="utf-8")
print("Successfully patched fact_extractor.py!")
