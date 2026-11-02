from pathlib import Path

path = Path("testkart_intelligence/extraction/fact_extractor.py")
content = path.read_text(encoding="utf-8")

old_p1 = r'r"(?:Dates?\s*(?:and\s*Time\s*)?of\s*(?:[A-Za-z\(\)\/\s]{0,40})?Examination|Revised\s*(?:examination\s*)?schedule|Schedule\s*of\s*(?:Computer\s*Based\s*)?(?:[A-Za-z0-9\(\)\/\s\-]{0,40})?Examination|Examination\s*Schedule|Time\s*Table|Schedule\s*of\s*CBT|CBT\s*Date|Date\s*of\s*Screening\s*Examination)\s*[:\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+(?:to|-)\s+[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}(?:\s*(?:to|-)\s*[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})?|(?:[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}\s+and\s+[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})|(?:(?:[0-9]{1,2}(?:st|nd|rd|th)?[,\s]+)+(?:and\s+)?[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})|(?:[A-Za-z]+,?\s+[0-9]{4})|(?:[A-Za-z]+[- ][A-Za-z]+,?\s+[0-9]{4}))"'

new_p1 = r'r"(?:Dates?\s*(?:and\s*Time\s*)?of\s*(?:[A-Za-z\(\)\/\s]{0,40})?Examination|Revised\s*(?:examination\s*)?schedule|Schedule\s*of\s*(?:tier[- ]?[a-zA-Z0-9]+\s*)?(?:\([^\)]+\)\s*)?(?:[A-Za-z0-9\(\)\/\s\-]{0,40})?Examination|Schedule\s*of\s*(?:tier[- ]?[a-zA-Z0-9]+\s*)?(?:\([^\)]+\)\s*)?|Examination\s*Schedule|Time\s*Table|Schedule\s*of\s*CBT|CBT\s*Date|Date\s*of\s*Screening\s*Examination)\s*[\):\-–]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+(?:to|-)\s+[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}(?:\s*(?:to|-)\s*[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})?|(?:[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4}\s+and\s+[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})|(?:(?:[0-9]{1,2}(?:st|nd|rd|th)?[,\s]+)+(?:and\s+)?[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})|(?:[A-Za-z]+,?\s+[0-9]{4})|(?:[A-Za-z]+[- ][A-Za-z]+,?\s+[0-9]{4}))"'

assert old_p1 in content, "Failed to find old_p1"
content = content.replace(old_p1, new_p1)
path.write_text(content, encoding="utf-8")
print("Updated line 80 pattern successfully!")
