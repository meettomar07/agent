import pymupdf
from testkart_intelligence.extraction.table_extractor import TableExtractor

doc = pymupdf.open('data/development_notices/dev_08_tnpsc_ctse_diploma_recruitment.pdf')
tables = TableExtractor.extract_tables_from_doc(doc)
for t in tables:
    header_str = " | ".join(t["header"]).lower()
    if any(k in header_str for k in ("maximum age", "minimum age", "age limit", "age concession")):
        header = [c.lower() for c in t["header"]]
        max_age_cols = [idx for idx, col in enumerate(header) if "maximum age" in col or "should not have" in col or "shouldnot have" in col]
        print("Max age cols in header:", max_age_cols)
        # Check rows
        age_counts = {}
        for r in t["rows"][1:]:
            for col_idx in max_age_cols:
                if col_idx < len(r) and r[col_idx].strip().isdigit():
                    val = int(r[col_idx].strip())
                    age_counts[val] = age_counts.get(val, 0) + 1
        print("Age counts in Max Age col:", age_counts)
        break
