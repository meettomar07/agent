import pymupdf

doc = pymupdf.open('data/new_validation_notices/new_val_16_tnpsc_research_assistant_in_the_inst.pdf')
# Check page 1 text for total vacancies
for pno in range(min(5, len(doc))):
    page = doc[pno]
    text = page.get_text()
    if 'vacanc' in text.lower() or 'total' in text.lower():
        print(f"\n=== Page {pno+1} ===")
        # Print lines with vacancy-related keywords
        for line in text.split('\n'):
            line_lower = line.lower()
            if any(k in line_lower for k in ['vacanc', 'total', 'post', 'sl no', 'sl.no']):
                print(f"  {line}")
