from testkart_intelligence.extraction.table_extractor import TableExtractor

tables = [{
    'page_number': 17,
    'table_index': 1,
    'header': ['S . No', 'Name of the Post', 'Post Code', 'Maximum Age (Should not have completed)', 'Age Concession Persons with Benchmark Disability', 'Ex-Servicemen', 'Destitute Widow'],
    'rows': [
        ['S . No', 'Name of the Post', 'Post Code', 'Maximum Age (Should not have completed)', 'Age Concession Persons with Benchmark Disability', 'Ex-Servicemen', 'Destitute Widow'],
        ['1', 'Motor Vehicle Inspector', '2119', '34', 'NA', '50', 'No Maximum Age Limit'],
        ['2', 'Draughtsman', '2114', '32', '42', '50', 'No Maximum Age Limit'],
        ['3', 'Surveyor', '3234', '32', '42', '50', 'No Maximum Age Limit'],
        ['4', 'Junior Draughting Officer', '3115', '32', '42', '32*', 'No Maximum Age Limit'],
    ]
}]

res = TableExtractor.parse_tables(tables)
print("Current age_limit:", res.age_limit)
