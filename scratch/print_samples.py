import json

with open('scratch/diagnosed_failures.json', 'r', encoding='utf-8') as f:
    items = json.load(f)

for rc in [
    'BIRTH_DATE_BRACKET_OR_TABLE_AGE_NOT_MATCHED',
    'QUALIFICATIONS_SPLIT_IN_TABLE_OR_APPENDIX',
    'EXAM_SCHEDULE_IN_TABLE_OR_FUTURE_INTIMATION',
    'SUBTOTAL_OR_CADRE_BREAKDOWN_MISTAKEN_FOR_TOTAL',
    'VACANCY_TABLE_NOT_PARSED',
]:
    print(f"\n*** {rc} ***")
    matches = [x for x in items if x['root_cause'] == rc]
    for x in matches[:5]:
        print(f"File: {x['notice_file']} | Field: {x['field_name']}")
        print(f"   GT:        {x['ground_truth']}")
        print(f"   Extracted: {x['extracted']}")
        print(f"   Detail:    {x['detail']}")
