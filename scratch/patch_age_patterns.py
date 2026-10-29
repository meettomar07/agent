"""Patch AGE_PATTERNS in fact_extractor.py to add birth-date window patterns."""

with open("testkart_intelligence/extraction/fact_extractor.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the AGE_PATTERNS block using a reliable landmark
start_marker = "    AGE_PATTERNS = [\n"
end_marker = "\n    ]\n\n    FEE_PATTERNS"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx)

if start_idx == -1 or end_idx == -1:
    print("ERROR: Could not find AGE_PATTERNS block")
    print("start_idx:", start_idx, "end_idx:", end_idx)
else:
    old_block = content[start_idx:end_idx + len("\n    ]\n")]
    print("Found block (first 200 chars):", repr(old_block[:200]))
    
    new_block = '''    AGE_PATTERNS = [
        r"(?:completed\\s*the\\s*age\\s*of\\s*([0-9]{2})\\s*years?\\s*and\\s*should\\s*not\\s*have\\s*completed\\s*([0-9]{2})\\s*years?(?:\\s*as\\s*on\\s*([0-9\\/.\\-]+))?)",
        r"(?:attained\\s*the\\s*age\\s*of\\s*([0-9]{2})\\s*years?\\s*and\\s*must\\s*not\\s*have\\s*(?:crossed|completed|attained)\\s*(?:the\\s*age\\s*of\\s*)?([0-9]{2})\\s*years?(?:\\s*(?:as\\s*on|on)\\s*([A-Za-z0-9\\/.\\-,\\s]+))?)",
        r"(?:age\\s*limit|age\\s*criteria|prescribed\\s*age)\\s*[:\\--]?\\s*([0-9]{2}\\s*(?:to|-)\\s*[0-9]{2}\\s*years?(?:[^\\.\\n]*?(?:as\\s*on\\s*[0-9\\/.\\-]+)?)?)",
        r"(?:between\\s*([0-9]{2}\\s*(?:to|and)\\s*[0-9]{2}\\s*years))",
        r"(?:not\\s*exceeding\\s*([0-9]{2})\\s*years(?:\\s*as\\s*on\\s*[^\\.\\n]+)?)",
        r"(?:not\\s*more\\s*than\\s*([0-9]{2})\\s*years(?:\\s*as\\s*on\\s*[^\\.\\n]+)?)",
        r"(?:maximum\\s*age\\s*(?:limit)?\\s*[:\\-]?\\s*([0-9]{2})\\s*years)",
        r"(?:minimum\\s*age\\s*[:\\-]?\\s*([0-9]{2})\\s*years?(?:.*?(?:maximum\\s*age\\s*[:\\-]?\\s*([0-9]{2})\\s*years?))?)",
        # Birth-date window: "born not earlier than DD.MM.YYYY and not later than DD.MM.YYYY"
        r"born\\s*not\\s*earlier\\s*than\\s*([0-9]{1,2}[./\\-][0-9]{1,2}[./\\-][0-9]{4})\\s*and\\s*not\\s*later\\s*than\\s*([0-9]{1,2}[./\\-][0-9]{1,2}[./\\-][0-9]{4})",
        # TNPSC style: "born after DD-MM-YYYY and on or before DD-MM-YYYY"
        r"born\\s*(?:on\\s*or\\s*)?after\\s*([0-9]{1,2}[./\\-][0-9]{1,2}[./\\-][0-9]{4})\\s*and\\s*(?:on\\s*or\\s*)?before\\s*([0-9]{1,2}[./\\-][0-9]{1,2}[./\\-][0-9]{4})",
        # Simple upper-age cap: "shall not have completed 35 years of age"
        r"shall\\s*not\\s*have\\s*completed\\s*([0-9]{2})\\s*years?\\s*of\\s*age",
    ]'''
    
    new_content = content[:start_idx] + new_block + content[end_idx + len("\n    ]\n"):]
    with open("testkart_intelligence/extraction/fact_extractor.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("AGE_PATTERNS patched successfully")
