import re
from pathlib import Path

# 1. Update fact_extractor.py
fe_path = Path("testkart_intelligence/extraction/fact_extractor.py")
fe_text = fe_path.read_text(encoding="utf-8")

# Insert multi-line exam date pattern if not present
new_exam_pat = '        r"(?:Date\\s*(?:and\\s*Time\\s*)?of\\s*(?:[A-Za-z\\(\\)\\/\\s]{0,40})?Examination|Examination\\s*Schedule|Schedule\\s*of\\s*Examination)[^\\n\\r]*[\\r\\n]+(?:[^\\n\\r]*[\\r\\n]+){0,10}?\\s*([0-9]{1,2}(?:st|nd|rd|th)?[\\/\\.\\-][0-9]{1,2}[\\/\\.\\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\\s+[A-Za-z]+\\s+[0-9]{4})",\n'
if "Date\\s*(?:and\\s*Time\\s*)?of" not in fe_text:
    target_idx = fe_text.find("EXAM_DATE_PATTERNS = [\n")
    if target_idx != -1:
        insert_pos = target_idx + len("EXAM_DATE_PATTERNS = [\n")
        fe_text = fe_text[:insert_pos] + new_exam_pat + fe_text[insert_pos:]
        print("Inserted new exam date pattern in fact_extractor.py")

# Insert below XX years age pattern if not present
new_age_pat = '        r"(?:age\\s*limit\\s*[:\\-–]?\\s*)?(?:below|under|not\\s*above)\\s*([0-9]{2})\\s*years?(?:\\s*of\\s*age)?(?:\\s*as\\s*on\\s*[^\\.\\n]+)?",\n'
if "below|under|not\\s*above" not in fe_text:
    target_idx = fe_text.find("AGE_PATTERNS = [\n")
    if target_idx != -1:
        insert_pos = target_idx + len("AGE_PATTERNS = [\n")
        fe_text = fe_text[:insert_pos] + new_age_pat + fe_text[insert_pos:]
        print("Inserted new age pattern in fact_extractor.py")

# Add qualification guard for boilerplate "order of studies"
old_qual_block = """                        val_str = " ".join(m.group(1).split()) if (len(m.groups()) >= 1 and m.group(1)) else " ".join(m.group(0).split())
                        val_str = re.sub(r"^(?:means,?\\s*|a\\s+pass\\s+in\\s+(?:the\\s+)?)+", "", val_str, flags=re.I).strip()"""

new_qual_block = """                        val_str = " ".join(m.group(1).split()) if (len(m.groups()) >= 1 and m.group(1)) else " ".join(m.group(0).split())
                        val_str = re.sub(r"^(?:means,?\\s*|a\\s+pass\\s+in\\s+(?:the\\s+)?)+", "", val_str, flags=re.I).strip()
                        if any(b in val_str.lower() for b in ["order of studies", "order of study", "pattern of study", "in the order of", "degree : institution : class"]):
                            continue"""

if "order of studies" not in fe_text:
    fe_text = fe_text.replace(old_qual_block, new_qual_block)
    print("Added boilerplate qualification guard in fact_extractor.py")

fe_path.write_text(fe_text, encoding="utf-8")

# 2. Update table_extractor.py
te_path = Path("testkart_intelligence/extraction/table_extractor.py")
te_text = te_path.read_text(encoding="utf-8")

# Let's inspect _parse_schedule_table and _parse_age_table replacements
old_schedule_code = """    @classmethod
    def _parse_schedule_table(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        \"\"\"Extract application start, closing, and exam dates from schedule tables.\"\"\"
        rows = table["rows"]
        pno = table["page_number"]

        for r in rows:
            if len(r) < 2:
                continue
            label = r[0].strip()
            label_lower = label.lower()
            val_text = " ".join(r[1:]).strip()
            cleaned_val_text = cls._clean_date_string(val_text)

            # 1. Application Schedule / Start & End Date
            if any(k in label_lower for k in ("submission of online", "online submission", "dates for submission", "date of notification", "application window", "commencement")):
                m_range = re.search(cls.DATE_RANGE_PATTERN, cleaned_val_text, re.IGNORECASE)
                if m_range and result.application_start_date is None:
                    result.application_start_date = m_range.group(1).strip()
                    result.application_end_date = m_range.group(2).strip()
                    ev = f"Schedule Table (Page {pno}): {label} : {val_text}"
                    result.application_start_evidence = ev
                    result.application_end_evidence = ev
                    result.application_start_page = pno
                    result.application_end_page = pno
                elif "notification" in label_lower and result.application_start_date is None:
                    m_single = re.search(cls.DATE_PATTERN, cleaned_val_text)
                    if m_single:
                        result.application_start_date = m_single.group(1).strip()
                        result.application_start_evidence = f"Schedule Table (Page {pno}): {label} : {val_text}"
                        result.application_start_page = pno

            elif any(k in label_lower for k in ("last date", "closing date", "upto", "up to")) and "payment" not in label_lower and "late" not in label_lower:
                if result.application_end_date is None:
                    m_single = re.search(cls.DATE_PATTERN, cleaned_val_text)
                    if m_single:
                        result.application_end_date = m_single.group(1).strip()
                        result.application_end_evidence = f"Schedule Table (Page {pno}): {label} : {val_text}"
                        result.application_end_page = pno

            # 2. Examination Dates & Stages
            elif any(k in label_lower for k in ("date of examination", "examination date", "schedule of cbt", "schedule of examination", "cbt date", "written examination", "date and time of written examination", "paper-i", "paper - i", "paper 1", "preliminary examination", "main examination")):
                m_range = re.search(cls.DATE_RANGE_PATTERN, cleaned_val_text, re.IGNORECASE)
                m_single = re.search(cls.DATE_PATTERN, cleaned_val_text)
                ex_date = None
                if m_range:
                    ex_date = f"{m_range.group(1).strip()} to {m_range.group(2).strip()}"
                elif m_single:
                    ex_date = m_single.group(1).strip()

                if ex_date:
                    stage = "General"
                    if "prelim" in label_lower or "tier-i" in label_lower or "tier 1" in label_lower or "paper-i" in label_lower:
                        stage = "Preliminary / Paper-I"
                    elif "main" in label_lower or "tier-ii" in label_lower or "tier 2" in label_lower or "paper-ii" in label_lower:
                        stage = "Mains / Paper-II"
                    elif "interview" in label_lower or "personality" in label_lower:
                        stage = "Interview"

                    result.exam_stages[stage] = ex_date
                    if result.exam_date is None:
                        result.exam_date = ex_date
                        result.exam_date_evidence = f"Schedule Table (Page {pno}): {label} : {val_text}"
                        result.exam_date_page = pno"""

new_schedule_code = """    @classmethod
    def _parse_schedule_table(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        \"\"\"Extract application start, closing, and exam dates from schedule tables.\"\"\"
        rows = table["rows"]
        pno = table["page_number"]
        last_section = None

        for r in rows:
            non_empty = [(i, c.strip()) for i, c in enumerate(r) if c and c.strip()]
            if not non_empty:
                continue
            
            # Determine label and value columns
            if len(non_empty) > 1 and re.match(r"^(?:[0-9]{1,2}|[A-Za-z]|\\(?[0-9a-zA-Z]\\)?)[.\\)]?$", non_empty[0][1]):
                label = non_empty[1][1]
                val_text = " ".join(c for i, c in non_empty if i > non_empty[1][0])
            elif r[0] and r[0].strip():
                label = r[0].strip()
                val_text = " ".join(r[1:]).strip()
            elif len(r) > 1 and r[1] and r[1].strip():
                label = r[1].strip()
                val_text = " ".join(r[2:]).strip()
            else:
                label = non_empty[0][1]
                val_text = " ".join(c for i, c in non_empty[1:])

            label_lower = label.lower()
            cleaned_val_text = cls._clean_date_string(val_text)

            # Update section context
            if any(k in label_lower for k in ("date of examination", "date and time of written", "date of written", "schedule of cbt", "schedule of examination")):
                last_section = "exam"
            elif any(k in label_lower for k in ("date of notification", "submission of online", "application window", "commencement")):
                last_section = "application"

            # 1. Application Schedule / Start & End Date
            if any(k in label_lower for k in ("submission of online", "online submission", "dates for submission", "date of notification", "application window", "commencement")):
                m_range = re.search(cls.DATE_RANGE_PATTERN, cleaned_val_text, re.IGNORECASE)
                if m_range and result.application_start_date is None:
                    result.application_start_date = m_range.group(1).strip()
                    result.application_end_date = m_range.group(2).strip()
                    ev = f"Schedule Table (Page {pno}): {label} : {val_text}"
                    result.application_start_evidence = ev
                    result.application_end_evidence = ev
                    result.application_start_page = pno
                    result.application_end_page = pno
                elif "notification" in label_lower and result.application_start_date is None:
                    m_single = re.search(cls.DATE_PATTERN, cleaned_val_text)
                    if m_single:
                        result.application_start_date = m_single.group(1).strip()
                        result.application_start_evidence = f"Schedule Table (Page {pno}): {label} : {val_text}"
                        result.application_start_page = pno

            elif any(k in label_lower for k in ("last date", "closing date", "upto", "up to")) and "payment" not in label_lower and "late" not in label_lower:
                if result.application_end_date is None:
                    m_single = re.search(cls.DATE_PATTERN, cleaned_val_text)
                    if m_single:
                        result.application_end_date = m_single.group(1).strip()
                        result.application_end_evidence = f"Schedule Table (Page {pno}): {label} : {val_text}"
                        result.application_end_page = pno

            # 2. Examination Dates & Stages
            is_exam_event = (
                any(k in label_lower for k in (
                    "date of examination", "examination date", "schedule of cbt", "schedule of examination",
                    "cbt date", "written examination", "date and time of written examination",
                    "preliminary examination", "main examination"
                ))
                or (last_section == "exam" and any(k in label_lower for k in ("paper", "stage", "tier", "prelim", "main")))
                or any(k in label_lower for k in ("paper-i", "paper - i", "paper – i", "paper 1", "paper i"))
            )
            if is_exam_event:
                m_range = re.search(cls.DATE_RANGE_PATTERN, cleaned_val_text, re.IGNORECASE)
                m_single = re.search(cls.DATE_PATTERN, cleaned_val_text)
                ex_date = None
                if m_range:
                    ex_date = f"{m_range.group(1).strip()} to {m_range.group(2).strip()}"
                elif m_single:
                    ex_date = m_single.group(1).strip()

                if ex_date:
                    stage = "General"
                    if any(k in label_lower for k in ("prelim", "tier-i", "tier 1", "paper-i", "paper - i", "paper – i", "paper i")):
                        stage = "Preliminary / Paper-I"
                    elif any(k in label_lower for k in ("main", "tier-ii", "tier 2", "paper-ii", "paper - ii", "paper – ii", "paper ii")):
                        stage = "Mains / Paper-II"
                    elif "interview" in label_lower or "personality" in label_lower:
                        stage = "Interview"

                    result.exam_stages[stage] = ex_date
                    if result.exam_date is None:
                        result.exam_date = ex_date
                        result.exam_date_evidence = f"Schedule Table (Page {pno}): {label} : {val_text}"
                        result.exam_date_page = pno"""

# Update age table parsing to prioritize General / 'Others' row and prevent min_age = 18 becoming max_age
old_age_code = """    @classmethod
    def _parse_age_table(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        \"\"\"Extract minimum and maximum age limit values from age tables.\"\"\"
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
                    result.age_limit_evidence = f"Age Table (Page {pno}): {row_str}"
                    result.age_limit_page = pno
                    return"""

new_age_code = """    @classmethod
    def _parse_age_table(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        \"\"\"Extract minimum and maximum age limit values from age tables.\"\"\"
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
                    result.age_limit_evidence = f"Age Table (Page {pno}) [General / Unreserved]: {row_str}"
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
                    result.age_limit_evidence = f"Age Table (Page {pno}): {row_str}"
                    result.age_limit_page = pno
                    return"""

# Normalize CRLF for matching
old_schedule_code_crlf = old_schedule_code.replace("\n", "\r\n")
old_age_code_crlf = old_age_code.replace("\n", "\r\n")

if old_schedule_code in te_text:
    te_text = te_text.replace(old_schedule_code, new_schedule_code)
    print("Replaced _parse_schedule_table (LF)")
elif old_schedule_code_crlf in te_text:
    te_text = te_text.replace(old_schedule_code_crlf, new_schedule_code.replace("\n", "\r\n"))
    print("Replaced _parse_schedule_table (CRLF)")
else:
    print("WARNING: Could not find old_schedule_code in table_extractor.py")

if old_age_code in te_text:
    te_text = te_text.replace(old_age_code, new_age_code)
    print("Replaced _parse_age_table (LF)")
elif old_age_code_crlf in te_text:
    te_text = te_text.replace(old_age_code_crlf, new_age_code.replace("\n", "\r\n"))
    print("Replaced _parse_age_table (CRLF)")
else:
    print("WARNING: Could not find old_age_code in table_extractor.py")

te_path.write_text(te_text, encoding="utf-8")
print("Finished applying improvements.")
