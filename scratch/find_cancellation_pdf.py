import os

files = os.listdir('data/documents')
matching = [f for f in files if 'Notice_20250514161031' in f or 'cancellation' in f.lower()]
print("Matching files:", matching)
