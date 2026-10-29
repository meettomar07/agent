from pathlib import Path

te_path = Path("testkart_intelligence/extraction/table_extractor.py")
te_text = te_path.read_text(encoding="utf-8")

old_age_def_idx = te_text.find("def _parse_age_table(")
assert old_age_def_idx != -1

new_age_func = '''    @classmethod
    def _parse_age_table(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        """Extract minimum and maximum age limit values from age tables."""
        rows = table["rows"]
        pno = table["page_number"]
        header = [c.lower() for c in table["header"]]

        # 1. First priority: Check for explicit General / 'Others' / Unreserved row
        for r in rows:
            row_str = " | ".join(r)
            row_lower = row_str.lower()
            if any(k in row_lower for k in ("‘others’", "“others”", "'others'", "others", "unreserved", "ur (general)", "general category")):
                m_age = re.findall(r"\\b([0-9]{2})\\b", row_str)
                valid_ages = [int(a) for a in m_age if 18 <= int(a) <= 65]
                upper_candidates = [a for a in valid_ages if 25 <= a <= 58]
                min_candidates = [a for a in valid_ages if 18 <= a <= 25]
                if upper_candidates and result.age_limit is None:
                    std_ages = [a for a in upper_candidates if 28 <= a <= 45]
                    max_age = std_ages[0] if std_ages else min(upper_candidates)
                    min_age = min_candidates[0] if min_candidates else 18
                    result.age_limit = f"{min_age} to {max_age} years"
                    result.age_limit_evidence = f"Age Table (Page {pno}) [General / Unreserved]: {row_str[:120]}"
                    result.age_limit_page = pno
                    return

        # 2. Second priority: Look for a dedicated 'Maximum Age' column across rows (excluding concessions)
        max_age_cols = [
            idx for idx, col in enumerate(header)
            if any(k in col for k in ("maximum age", "should not have", "shouldnot have", "age limit"))
            and "concession" not in col
        ]
        if max_age_cols:
            from collections import Counter
            col_ages = []
            for r in rows[1:]:
                r_text = " ".join(r).lower()
                is_relaxation_row = any(k in r_text for k in ("sc/st", "scs", "sts", "mbc", "destitute", "widow", "disability", "ex-service"))
                if is_relaxation_row:
                    continue
                for c_idx in max_age_cols:
                    if c_idx < len(r):
                        m = re.search(r"\\b([0-9]{2})\\b", r[c_idx])
                        if m:
                            num = int(m.group(1))
                            if 25 <= num <= 45:
                                col_ages.append(num)
            if col_ages and result.age_limit is None:
                counts = Counter(col_ages)
                modal_age = counts.most_common(1)[0][0]
                result.age_limit = f"18 to {modal_age} years"
                result.age_limit_evidence = f"Age Table (Page {pno}): General category maximum age {modal_age} years across {len(col_ages)} cadre rows"
                result.age_limit_page = pno
                return

        # 3. Fallback: row-by-row scanning with strict lower bound (never emit <= 21 as maximum age)
        for r in rows:
            row_str = " | ".join(r)
            row_lower = row_str.lower()
            if any(k in row_lower for k in ("maximum", "should not have completed", "age limit")):
                m_age = re.findall(r"\\b([0-9]{2})\\b", row_str)
                valid_ages = [int(a) for a in m_age if 18 <= int(a) <= 65]
                upper_candidates = [a for a in valid_ages if 25 <= a <= 58]
                min_candidates = [a for a in valid_ages if 18 <= a <= 25]
                if upper_candidates and result.age_limit is None:
                    std_ages = [a for a in upper_candidates if 28 <= a <= 45]
                    max_age = std_ages[0] if std_ages else min(upper_candidates)
                    min_age = min_candidates[0] if min_candidates else 18
                    result.age_limit = f"{min_age} to {max_age} years"
                    result.age_limit_evidence = f"Age Table (Page {pno}): {row_str[:120]}"
                    result.age_limit_page = pno
                    return
'''

# Find start of classmethod before def _parse_age_table
cm_idx = te_text.rfind("    @classmethod", 0, old_age_def_idx)
te_text = te_text[:cm_idx] + new_age_func
te_path.write_text(te_text, encoding="utf-8")
print("Successfully replaced _parse_age_table.")
