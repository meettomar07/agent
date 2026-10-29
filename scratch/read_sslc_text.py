import pymupdf

doc = pymupdf.open('data/development_notices/dev_13_tnpsc_special_competitive_exam.pdf')
text = doc[3].get_text() # Page 4
idx = text.find('Secondary School')
print(repr(text[idx-50:idx+250]))
