with open('scratch/evaluate_development_set.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('for f in facts_list:')
print(text[idx-50:idx+400])
