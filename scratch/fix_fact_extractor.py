path = 'testkart_intelligence/extraction/fact_extractor.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
old = 'if "total_vacancies" not in extracted_keys and tbl_res.total_vacancies and not is_compilation:'
new = 'if "total_vacancies" not in extracted_keys and tbl_res.total_vacancies:'
if old in text:
    text = text.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated successfully')
else:
    print('old pattern not found')
