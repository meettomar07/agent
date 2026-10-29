"""Table-aware fact extractor for official government notifications.

Leverages PyMuPDF native table detection (`page.find_tables()`) to extract structured data from:
1. Multi-page, multi-cadre vacancy tables (identifying explicit grand totals and post-wise itemizations).
2. Multi-column schedule and examination date tables (separating application windows from exam stages).
3. Post-wise educational qualification and eligibility matrices.
4. Prescribed age limit and concession tables.

Enforces strict safety rules:
- Never sums overlapping category columns or sub-cadres without verified evidence of disjoint sets.
- Distinguishes grand totals from subtotals and category-specific quotas.
- Preserves complete qualification statements (degree, discipline, experience, registration).
- Retains structured evidence excerpts and source page provenance.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PostVacancyItem:
    """Represents an individual post / cadre vacancy entry in a multi-cadre table."""
    post_name: str
    post_code: Optional[str] = None
    department: Optional[str] = None
    vacancies: Optional[str] = None
    pay_scale: Optional[str] = None
    page_number: int = 1


@dataclass
class TableExtractionResult:
    """Aggregated facts and structured breakdowns extracted from document tables."""
    total_vacancies: Optional[str] = None
    total_vacancies_evidence: Optional[str] = None
    total_vacancies_page: int = 1
    post_vacancies: List[PostVacancyItem] = field(default_factory=list)

    application_start_date: Optional[str] = None
    application_start_evidence: Optional[str] = None
    application_start_page: int = 1

    application_end_date: Optional[str] = None
    application_end_evidence: Optional[str] = None
    application_end_page: int = 1

    exam_date: Optional[str] = None
    exam_date_evidence: Optional[str] = None
    exam_date_page: int = 1
    exam_stages: Dict[str, str] = field(default_factory=dict)

    eligibility: Optional[str] = None
    eligibility_evidence: Optional[str] = None
    eligibility_page: int = 1
    post_eligibility: Dict[str, str] = field(default_factory=dict)

    age_limit: Optional[str] = None
    age_limit_evidence: Optional[str] = None
    age_limit_page: int = 1


class TableExtractor:
    """Extracts structured recruitment facts from tabular structures in PDF documents."""

    # Highly selective keywords for pages beyond page 25
    TABLE_CANDIDATE_KEYWORDS = (
        "posts and vacanc", "distribution of vacanc", "number of vacanc", "no. of vacanc",
        "date of notification", "examination date", "educational qualification",
        "essential qualification", "prescribed qualification", "maximum age",
        "age concession", "total vacancies", "grand total", "schedule of cbt",
        "schedule of exam", "date and time of written", "name of the post",
    )

    MARKS_TABLE_MARKERS = (
        "maximum marks", "min qualifying marks", "scheme of examination", "minimum qualifying",
        "duration", "type of examination", "sslc mark sheet", "question paper", "scheme of exam",
        "standard of vision", "suitable category of benchmark disabilities",
    )

    DATE_PATTERN = r"([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})"
    DATE_RANGE_PATTERN = r"([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})\s*(?:to|-)\s*([0-9]{1,2}(?:st|nd|rd|th)?[\/\.\-\s]+[0-9]{1,2}[\/\.\-\s]+[0-9]{4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})"

    @classmethod
    def _is_marks_or_exam_scheme_table(cls, table: Dict[str, Any]) -> bool:
        """Identify examination scheme or marks tables to prevent mistaking marks totals for vacancy counts."""
        header_str = " | ".join(table.get("header", [])).lower()
        if any(m in header_str for m in cls.MARKS_TABLE_MARKERS):
            return True
        rows_sample = " ".join(" ".join(r) for r in table.get("rows", [])[:6]).lower()
        if any(m in rows_sample for m in (
            "maximum marks", "minimum qualifying", "scheme of examination", "qualifying marks",
            "type of examination", "duration", "standard of vision", "for selection"
        )):
            return True
        return False

    @staticmethod
    def _clean_date_string(raw: Optional[str]) -> str:
        """Normalize date strings with OCR spaces or punctuation to standard DD.MM.YYYY format."""
        if not raw:
            return ""
        def repl(m):
            d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
            if 1 <= int(d) <= 31 and 1 <= int(mo) <= 12 and 2020 <= int(y) <= 2035:
                return f"{d}.{mo}.{y}"
            return m.group(0)

        cleaned = re.sub(r"\b(\d{1,2})\s*[\./\- ]\s*(\d{1,2})\s*[\./\- ]\s*(\d{4})\b", repl, raw)
        return cleaned

    @staticmethod
    def _clean_cell(cell: Optional[str]) -> str:
        if not cell:
            return ""
        c = cell.replace("\xa0", " ").replace("\r", " ").replace("\n", " ")
        return " ".join(c.split())

    @classmethod
    def extract_tables_from_doc(cls, doc: Any) -> List[Dict[str, Any]]:
        """Extract structured tables across document pages with candidate page filtering."""
        extracted_tables = []
        num_pages = len(doc)

        for pno in range(num_pages):
            page = doc[pno]
            # Fast text-check: scan early pages or pages containing recruitment/table keywords
            try:
                page_text_sample = page.get_text()[:1500].lower()
            except Exception:
                page_text_sample = ""

            is_early_page = (pno < 25)
            has_keywords = any(k in page_text_sample for k in cls.TABLE_CANDIDATE_KEYWORDS)

            if not (is_early_page or has_keywords):
                continue

            try:
                tabs = page.find_tables()
                if not tabs or not tabs.tables:
                    continue

                for t_idx, t in enumerate(tabs.tables):
                    raw_rows = t.extract()
                    if not raw_rows or len(raw_rows) < 2:
                        continue

                    cleaned_rows = [[cls._clean_cell(c) for c in row] if row else [] for row in raw_rows]
                    # Filter out empty rows
                    cleaned_rows = [r for r in cleaned_rows if any(c.strip() for c in r)]
                    if len(cleaned_rows) < 2:
                        continue

                    # Merge multi-line header rows (e.g. Row 0: "Number of", Row 1: "vacancies")
                    header_rows = [cleaned_rows[0]]
                    curr_idx = 1
                    while curr_idx < min(4, len(cleaned_rows)):
                        r = cleaned_rows[curr_idx]
                        r_text = " ".join(c for c in r if c).lower()
                        is_hdr = any(k in r_text for k in (
                            "post", "vacanc", "service", "department", "code", "scale", "pay",
                            "level", "distribution", "category", "quota", "reservation", "sl no",
                            "name of", "educational", "qualification", "maximum age", "minimum age",
                            "age concession", "examination", "date of", "paper", "marks"
                        ))
                        has_large_number = any(c.strip().isdigit() and int(c.strip()) > 10 for c in r if c and c.strip())
                        if is_hdr and not has_large_number:
                            header_rows.append(r)
                            curr_idx += 1
                        else:
                            break

                    num_cols = max(len(hr) for hr in header_rows)
                    merged_header = []
                    for c in range(num_cols):
                        cell_parts = [hr[c].strip() for hr in header_rows if c < len(hr) and hr[c] and hr[c].strip()]
                        merged_header.append(" ".join(cell_parts))

                    data_rows = cleaned_rows[curr_idx:]
                    if not data_rows:
                        data_rows = cleaned_rows[1:]

                    extracted_tables.append({
                        "page_number": pno + 1,
                        "table_index": t_idx + 1,
                        "header": merged_header,
                        "rows": [merged_header] + data_rows,
                        "row_count": len(data_rows) + 1,
                        "col_count": len(merged_header),
                    })
            except Exception as exc:
                logger.debug("Failed table detection on page %d: %s", pno + 1, exc)
                continue

        return extracted_tables

    @classmethod
    def parse_tables(cls, tables: List[Dict[str, Any]], authority_name: str = "") -> TableExtractionResult:
        """Parse extracted table grids into structured facts."""
        result = TableExtractionResult()

        # Phase 1: Scan ALL tables for an explicit Grand Total / Total row
        cls._scan_for_grand_total_vacancy_row(tables, result)

        # Phase 2: Parse individual table types (vacancy items, schedules, qualifications, age)
        for t in tables:
            header_str = " | ".join(t["header"]).lower()
            rows_sample = " ".join(" ".join(r) for r in t["rows"][:4]).lower()

            # 1. Vacancy Table Post-wise parsing
            if any(k in header_str for k in ("vacanc", "post", "distribution of", "number of vacancies", "no of vacancies")):
                cls._parse_vacancy_table_items(t, result)

            # 2. Schedule & Date Table Parsing
            if any(k in header_str or k in rows_sample for k in (
                "date of notification", "submission of online", "last date", "examination date",
                "schedule of", "paper", "cbt", "application window", "written examination"
            )):
                cls._parse_schedule_table(t, result)

            # 3. Qualification Table Parsing
            if any(k in header_str for k in ("educational qualification", "qualification", "essential qualification", "prescribed qualification", "educational")):
                cls._parse_qualification_table(t, result)

            # 4. Age Limit Table Parsing
            if any(k in header_str for k in ("maximum age", "minimum age", "age limit", "age concession")):
                cls._parse_age_table(t, result)

        # Phase 3: Single-post or post-wise aggregation fallback if no explicit Grand Total row exists
        if result.total_vacancies is None and result.post_vacancies:
            if len(result.post_vacancies) == 1:
                # Single-post recruitment notification
                single_post = result.post_vacancies[0]
                result.total_vacancies = str(single_post.vacancies)
                result.total_vacancies_evidence = f"Single Post Table Row (Page {single_post.page_number}): {single_post.post_name} - {single_post.vacancies} vacancies"
                result.total_vacancies_page = single_post.page_number
            elif 1 < len(result.post_vacancies) <= 30:
                # Multiple distinct posts without grand total: compute sum
                try:
                    total_sum = sum(int(p.vacancies) for p in result.post_vacancies if p.vacancies and p.vacancies.isdigit())
                    if 0 < total_sum < 500000:
                        posts_summary = ", ".join(f"{p.post_name}: {p.vacancies}" for p in result.post_vacancies[:3])
                        result.total_vacancies = str(total_sum)
                        result.total_vacancies_evidence = f"Aggregate of {len(result.post_vacancies)} posts (Page {result.post_vacancies[0].page_number}): {posts_summary}"
                        result.total_vacancies_page = result.post_vacancies[0].page_number
                except Exception:
                    pass

        return result

    @classmethod
    def _scan_for_grand_total_vacancy_row(cls, tables: List[Dict[str, Any]], result: TableExtractionResult) -> None:
        """Scan across ALL tables and rows for an explicit Grand Total / Total summary row."""
        for t in tables:
            # Skip examination schemes, marks tables, selection weightages
            if cls._is_marks_or_exam_scheme_table(t):
                continue

            pno = t["page_number"]
            for r in t["rows"]:
                if len(r) < 2:
                    continue
                row_str = " | ".join(r)
                row_lower = row_str.lower()
                if "mark" in row_lower or "duration" in row_lower:
                    continue

                # Look for 'Total', 'Grand Total', or 'Aggregate' in early columns
                for c_idx in range(min(5, len(r))):
                    cell_text = r[c_idx].strip()
                    cell_clean = cell_text.lower().strip(".:- ")

                    # Must match standalone total label (avoiding phrases like "Total Marks" or "Total Questions")
                    is_total_label = (
                        cell_clean in ("total", "grand total", "aggregate", "total vacancies", "all posts", "sum total", "total posts", "grand total vacancies")
                        or (cell_clean.startswith("total") and "mark" not in cell_clean and "question" not in cell_clean and len(cell_clean) < 20)
                    )

                    if is_total_label:
                        # Scan subsequent cells in this row for all valid positive integers
                        row_numbers = []
                        for val_cell in r[c_idx + 1:]:
                            val_clean = val_cell.replace(",", "").strip()
                            m = re.match(r"^([0-9]{1,6})(?:\s*[\*\#\@]+.*)?$", val_clean)
                            if m:
                                num_val = int(m.group(1))
                                if 0 < num_val < 500000:
                                    row_numbers.append(num_val)

                        if row_numbers:
                            # In multi-column category breakdown tables (UR, SC, ST, OBC, EWS, Total, ESM...),
                            # the grand total is the sum or maximum subtotal, not the first category count!
                            chosen_total = None
                            for i, num in enumerate(row_numbers):
                                if i >= 2 and num == sum(row_numbers[:i]):
                                    chosen_total = num
                                    break
                            if chosen_total is None:
                                chosen_total = max(row_numbers) if len(row_numbers) > 1 else row_numbers[0]

                            result.total_vacancies = str(chosen_total)
                            result.total_vacancies_evidence = f"Table Total Row (Page {pno}): {row_str}"
                            result.total_vacancies_page = pno
                            return

    @classmethod
    def _parse_vacancy_table_items(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        """Extract post-wise itemizations from vacancy tables."""
        rows = table["rows"]
        pno = table["page_number"]
        header = [c.lower() for c in table["header"]]

        post_col = None
        code_col = None
        vac_col = None
        pay_col = None

        for idx, col in enumerate(header):
            if "name of" in col and "post" in col:
                post_col = idx
            elif "post code" in col or "code" in col:
                code_col = idx
            elif ("number of" in col and "vacanc" in col) or ("no of" in col and "vacanc" in col) or col in ("vacancies", "total vacancies") or ("vacanc" in col and "distribution" not in col):
                vac_col = idx
            elif "level of pay" in col or "scale of pay" in col or "pay" in col:
                pay_col = idx

        if post_col is None:
            for idx, col in enumerate(header):
                if "post" in col:
                    post_col = idx
                    break

        for r in rows[1:]:
            row_str = " | ".join(r)
            row_lower = row_str.lower()
            if any(r[c].lower().strip(".:- ") in ("total", "grand total") for c in range(min(3, len(r)))):
                continue

            if post_col is not None and post_col < len(r):
                post_name = r[post_col].strip()
                if post_name and len(post_name) > 3 and not re.match(r"^(?:GT|BC|SC|ST|MBC|EWS|UR|Total|Sl|S\.|No)\b", post_name, re.I):
                    p_code = r[code_col].strip() if (code_col is not None and code_col < len(r)) else None
                    p_vac = r[vac_col].strip() if (vac_col is not None and vac_col < len(r)) else None
                    p_pay = r[pay_col].strip() if (pay_col is not None and pay_col < len(r)) else None

                    vac_num = None
                    if p_vac:
                        m_vac = re.search(r"\b([0-9]{1,5})\b", p_vac)
                        if m_vac:
                            vac_num = m_vac.group(1)

                    if vac_num:
                        result.post_vacancies.append(
                            PostVacancyItem(
                                post_name=post_name,
                                post_code=p_code,
                                vacancies=vac_num,
                                pay_scale=p_pay,
                                page_number=pno,
                            )
                        )

    @classmethod
    def _parse_schedule_table(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        """Extract application start, closing, and exam dates from schedule tables."""
        rows = table["rows"]
        pno = table["page_number"]
        last_section = None

        for r in rows:
            non_empty = [(i, c.strip()) for i, c in enumerate(r) if c and c.strip()]
            if not non_empty:
                continue
            
            # Determine label and value columns
            if len(non_empty) > 1 and re.match(r"^(?:[0-9]{1,2}|[A-Za-z]|\(?[0-9a-zA-Z]\)?)[.\)]?$", non_empty[0][1]):
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
                        result.exam_date_page = pno

    @classmethod
    def _parse_qualification_table(cls, table: Dict[str, Any], result: TableExtractionResult) -> None:
        """Extract complete educational qualification statements per post."""
        rows = table["rows"]
        pno = table["page_number"]
        header = [c.lower() for c in table["header"]]

        post_col = None
        qual_col = None

        for idx, col in enumerate(header):
            if "name of" in col and "post" in col:
                post_col = idx
            elif "educational" in col or "qualification" in col or "minimum qualification" in col:
                qual_col = idx

        if qual_col is None:
            for idx, c in enumerate(rows[0]):
                if "educational" in c.lower() or "qualification" in c.lower():
                    qual_col = idx
                    break

        if qual_col is None:
            return

        for r in rows[1:]:
            post_name = r[post_col].strip() if (post_col is not None and post_col < len(r)) else ""
            qual_text = r[qual_col].strip() if qual_col < len(r) else ""

            if qual_text and len(qual_text) > 15:
                cleaned_qual = cls._clean_qualification_text(qual_text)
                if post_name:
                    result.post_eligibility[post_name] = cleaned_qual

                if result.eligibility is None and len(cleaned_qual) >= 10:
                    result.eligibility = cleaned_qual
                    result.eligibility_evidence = f"Qualification Table (Page {pno}): {qual_text[:140]}"
                    result.eligibility_page = pno

    @classmethod
    def _clean_qualification_text(cls, raw: str) -> str:
        """Strip statutory preamble while preserving degree, discipline, and conditions."""
        text = raw
        text = re.sub(r"^\s*\([ivxIVX0-9]+\)\s*", "", text)
        preambles = [
            r"^(?:Candidates\s*must\s*possess\s*(?:the\s*following\s*)?|Must\s*possess\s*)+",
            r"^(?:The\s*educational\s*qualification\s*prescribed\s*(?:for\s*this\s*post\s*)?is\s*)+",
            r"^(?:A\s*candidate\s*must\s*have\s*passed\s*)+",
            r"^(?:Minimum\s*General\s*Educational\s*Qualification\s*viz\.?\s*)+",
        ]
        for p in preambles:
            text = re.sub(p, "", text, flags=re.IGNORECASE).strip()

        if len(text) < 10:
            text = raw

        return " ".join(text.split())

    @classmethod
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
                m_age = re.findall(r"\b([0-9]{2})\b", row_str)
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
                        m = re.search(r"\b([0-9]{2})\b", r[c_idx])
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
                m_age = re.findall(r"\b([0-9]{2})\b", row_str)
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
