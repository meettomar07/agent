path = 'testkart_intelligence/extraction/verifier.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

old = '''                    elif any(p_term in ev for p_term in ("post of", "posts of", "assistant", "deputy", "director", "officer", "lecturer", "professor")) and not any(tot in ev for tot in ("total", "grand total", "aggregate")):
                        if re.search(r"posts advertised|name of post|tabular", full_text, re.IGNORECASE):
                            vac_f.status = "POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW"
                            vac_f.notes = f"Extracted value {vac_f.value} appears to be a post-specific vacancy count rather than aggregate total"'''

new = '''                    elif any(p_term in ev for p_term in ("assistant", "deputy", "director", "officer", "lecturer", "professor")) and not any(tot in ev for tot in ("total", "grand total", "aggregate", "posts of", "post of", "posts:")):
                        if re.search(r"distribution of vacancies|breakup of vacancies", full_text, re.IGNORECASE):
                            vac_f.status = "POST_WISE_BREAKDOWN_FLAGGED_FOR_REVIEW"
                            vac_f.notes = f"Extracted value {vac_f.value} appears to be a post-specific vacancy count rather than aggregate total"'''

if old in text:
    text = text.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated verifier.py successfully')
else:
    print('Pattern not found in verifier.py')
