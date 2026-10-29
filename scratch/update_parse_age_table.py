with open('testkart_intelligence/extraction/table_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

replacement = '''    @classmethod
    def _parse_age_table(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        """Extract minimum and maximum age limit values from age tables."""
        rows = table["rows"]
        pno = table["page_number"]
        header = [c.lower() for c in table["header"]]

        # 1. First attempt: Look for a dedicated 'Maximum Age' column across rows
        max_age_cols = [
            idx for idx, col in enumerate(header)
            if any(k in col for k in ("maximum age", "should not have", "shouldnot have", "age limit"))
            and "concession" not in col
        ]
        if max_age_cols:
            from collections import Counter
            col_ages = []
            for r in rows[1:]:
                for c_idx in max_age_cols:
                    if c_idx < len(r):
                        m = re.search(r"\\b([0-9]{2})\\b", r[c_idx])
                        if m:
                            num = int(m.group(1))
                            if 21 <= num <= 45:
                                col_ages.append(num)
            if col_ages and result.age_limit is None:
                # Use majority/modal age across posts for general category
                counts = Counter(col_ages)
                modal_age = counts.most_common(1)[0][0]
                result.age_limit = f"18 to {modal_age} years"
                result.age_limit_evidence = f"Age Table (Page {pno}): General category maximum age {modal_age} years across {len(col_ages)} cadre rows"
                result.age_limit_page = pno
                return

        # 2. Fallback: row-by-row scanning
        for r in rows:
            row_str = " | ".join(r)
            row_lower = row_str.lower()
            if "maximum" in row_lower or "should not have completed" in row_lower or "age limit" in row_lower:
                m_age = re.findall(r"\\b([0-9]{2})\\b", row_str)
                valid_ages = [int(a) for a in m_age if 18 <= int(a) <= 65]
                if valid_ages and result.age_limit is None:
                    # Prefer unreserved standard age in 21..45 range
                    std_ages = [a for a in valid_ages if 21 <= a <= 45]
                    max_age = std_ages[0] if std_ages else max(valid_ages)
                    min_candidates = [a for a in valid_ages if 18 <= a <= 21]
                    min_age = min_candidates[0] if min_candidates else 18
                    if min_age != max_age:
                        result.age_limit = f"{min_age} to {max_age} years"
                    else:
                        result.age_limit = f"Not exceeding {max_age} years"
                    result.age_limit_evidence = f"Age Table (Page {pno}): {row_str[:120]}"
                    result.age_limit_page = pno
                    break'''

target = '''    @classmethod
    def _parse_age_table(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        """Extract minimum and maximum age limit values from age tables."""
        rows = table["rows"]
        pno = table["page_number"]

        for r in rows:
            row_str = " | ".join(r)
            row_lower = row_str.lower()
            if "maximum" in row_lower or "should not have completed" in row_lower or "age limit" in row_lower:
                m_age = re.findall(r"\\b([0-9]{2})\\b", row_str)
                valid_ages = [int(a) for a in m_age if 18 <= int(a) <= 65]
                if valid_ages and result.age_limit is None:
                    # Prefer unreserved standard age in 21..45 range (first unreserved bracket in column order)
                    std_ages = [a for a in valid_ages if 21 <= a <= 45]
                    max_age = std_ages[0] if std_ages else max(valid_ages)
                    min_candidates = [a for a in valid_ages if 18 <= a <= 21]
                    min_age = min_candidates[0] if min_candidates else 18
                    if min_age != max_age:
                        result.age_limit = f"{min_age} to {max_age} years"
                    else:
                        result.age_limit = f"Not exceeding {max_age} years"
                    result.age_limit_evidence = f"Age Table (Page {pno}): {row_str[:120]}"
                    result.age_limit_page = pno
                    break'''

# Let's check if target is in text (handling raw string vs escapes)
if "_parse_age_table" in text:
    idx = text.find("    @classmethod\n    def _parse_age_table")
    end_idx = text.find("    @classmethod", idx + 20)
    if end_idx == -1:
        end_idx = len(text)
    old_block = text[idx:end_idx].rstrip()
    text = text[:idx] + replacement + "\n" + text[end_idx:]
    with open('testkart_intelligence/extraction/table_extractor.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Successfully replaced _parse_age_table in table_extractor.py")
else:
    print("Could not find _parse_age_table in file")
