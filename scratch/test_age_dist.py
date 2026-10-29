from collections import Counter
import re

rows = [
    ['S . No', 'Name of the Post', 'Post Code', 'Maximum Age (Should not have completed)', 'Age Concession Persons with Benchmark Disability', 'Ex-Servicemen', 'Destitute Widow'],
    ['1', 'Motor Vehicle Inspector', '2119', '34', 'NA', '50', 'No Maximum Age Limit'],
    ['2', 'Draughtsman', '2114', '32', '42', '50', 'No Maximum Age Limit'],
    ['3', 'Surveyor', '3234', '32', '42', '50', 'No Maximum Age Limit'],
    ['4', 'Junior Draughting Officer', '3115', '32', '42', '32*', 'No Maximum Age Limit'],
]

header = [c.lower() for c in rows[0]]
max_age_cols = [idx for idx, col in enumerate(header) if any(k in col for k in ("maximum age", "should not have", "shouldnot have", "age limit")) and "concession" not in col]
print("Max age cols:", max_age_cols)

col_ages = []
for r in rows[1:]:
    for c_idx in max_age_cols:
        if c_idx < len(r):
            m = re.search(r"\b([0-9]{2})\b", r[c_idx])
            if m and 18 <= int(m.group(1)) <= 65:
                col_ages.append(int(m.group(1)))

print("Col ages:", col_ages)
counts = Counter(col_ages)
most_common_age = counts.most_common(1)[0][0]
print("Most common general age limit:", most_common_age)
