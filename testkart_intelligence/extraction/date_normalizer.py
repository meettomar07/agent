"""Date normalization, OCR error correction, and multi-format parser for Indian government notices."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dateutil import parser as date_parser


class DateNormalizer:
    """Robust normalizer for Indian government recruitment and examination dates."""

    MONTH_MAP = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    @classmethod
    def clean_ocr_date_string(cls, text: str) -> str:
        """Correct standard OCR substitution errors in numeric date expressions.

        Transforms strings like 'l5.ll.2O26' -> '15.11.2026', 'O1/O8/2O26' -> '01/08/2026'.
        Retains alphabetical month names untouched.
        """
        if not text:
            return ""
        cleaned = text.strip()

        # Fix broken ordinal indicators first: e.g. "15th November 2026" -> "15 November 2026"
        cleaned = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)\b", r"\1", cleaned, flags=re.IGNORECASE)

        # Fix broken separators: e.g. "15 . 11 . 2026" -> "15.11.2026", "15..11..2026" -> "15.11.2026"
        cleaned = re.sub(r"\.{2,}", ".", cleaned)
        cleaned = re.sub(r"-{2,}", "-", cleaned)

        # Detect candidate date chunks with potential OCR errors:
        # e.g. "l5.ll.2O26" or "O1/O8/2O26" or "3l-l2-2O26"
        def _replace_ocr_chunk(m: re.Match) -> str:
            raw_chunk = m.group(0)
            # Map common OCR character substitutions
            trans = raw_chunk.translate(str.maketrans({
                'O': '0', 'o': '0',
                'l': '1', 'I': '1', '|': '1',
                'S': '5', 's': '5',
                'B': '8',
            }))
            return trans

        # Pattern for numeric date token with OCR noise: e.g. [0-9OolIS]{1,2}[\.\/\-][0-9OolIS]{1,2}[\.\/\-][0-9OolIS]{4}
        ocr_date_pat = re.compile(r"\b[0-9OolIS\|]{1,2}[\.\/\-][0-9OolIS\|]{1,2}[\.\/\-][0-9OolIS\|]{4}\b")
        cleaned = ocr_date_pat.sub(_replace_ocr_chunk, cleaned)

        return cleaned

    @classmethod
    def normalize_single_date(cls, raw_date_str: str) -> Optional[str]:
        """Normalize a single date string to standard ISO format (YYYY-MM-DD or YYYY-MM).

        Supports Indian formats:
        - DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY
        - DD Month YYYY (e.g. '15 November 2026')
        - Month YYYY (e.g. 'December 2026') -> '2026-12'
        """
        if not raw_date_str or len(raw_date_str.strip()) < 4:
            return None

        cleaned = cls.clean_ocr_date_string(raw_date_str)

        # 1. Check for Month YYYY: e.g. "December 2026" or "Dec 2026"
        m_month_year = re.match(
            r"^(?:in\s+)?([A-Za-z]+),?\s+([0-9]{4})$",
            cleaned.strip(),
            re.IGNORECASE,
        )
        if m_month_year:
            m_name = m_month_year.group(1).lower()
            year_str = m_month_year.group(2)
            if m_name in cls.MONTH_MAP:
                return f"{year_str}-{cls.MONTH_MAP[m_name]:02d}"

        # 2. Check for DD.MM.YYYY or DD/MM/YYYY or DD-MM-YYYY
        m_dmy = re.search(
            r"\b([0-9]{1,2})[\.\/\-]([0-9]{1,2})[\.\/\-]([0-9]{4})\b",
            cleaned,
        )
        if m_dmy:
            day, month, year = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
            # Validate day and month ranges
            if 1 <= month <= 12 and 1 <= day <= 31 and 2000 <= year <= 2099:
                try:
                    dt = datetime(year, month, day)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    pass

        # 3. Check for DD Month YYYY: e.g. "15 November 2026" or "15 Nov 2026"
        m_d_month_y = re.search(
            r"\b([0-9]{1,2})\s+([A-Za-z]+),?\s+([0-9]{4})\b",
            cleaned,
        )
        if m_d_month_y:
            day_str = m_d_month_y.group(1)
            month_str = m_d_month_y.group(2).lower()
            year_str = m_d_month_y.group(3)
            if month_str in cls.MONTH_MAP:
                try:
                    dt = datetime(int(year_str), cls.MONTH_MAP[month_str], int(day_str))
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    pass

        # 4. Fallback to python-dateutil with dayfirst=True
        try:
            # Strip procedural trailing text like "(23:50 Hours)" or "upto 5:00 PM"
            time_stripped = re.sub(r"\(?[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\s*(?:AM|PM|hrs|hours|pm|am)?\)?", "", cleaned, flags=re.IGNORECASE)
            time_stripped = re.sub(r"\b(?:upto|up\s*to|till|at)\s*.*$", "", time_stripped, flags=re.IGNORECASE).strip()
            parsed = date_parser.parse(time_stripped, dayfirst=True, fuzzy=True)
            if 2000 <= parsed.year <= 2099:
                return parsed.strftime("%Y-%m-%d")
        except Exception:
            pass

        return None

    @classmethod
    def normalize_date_range(cls, raw_range_str: str) -> Optional[str]:
        """Normalize a date range string like '24.06.2026 to 24.07.2026' into '2026-06-24 to 2026-07-24'."""
        if not raw_range_str:
            return None

        # Split on 'to' or '–' or '-'
        parts = re.split(r"\s+(?:to|-|–)\s+", raw_range_str.strip(), flags=re.IGNORECASE)
        if len(parts) == 2:
            start_iso = cls.normalize_single_date(parts[0])
            end_iso = cls.normalize_single_date(parts[1])
            if start_iso and end_iso:
                return f"{start_iso} to {end_iso}"
            elif start_iso:
                return start_iso
            elif end_iso:
                return end_iso

        return cls.normalize_single_date(raw_range_str)

    @classmethod
    def normalize_recruitment_value(cls, fact_key: str, raw_value: str) -> Optional[str]:
        """Normalize any recruitment fact value into a standardized representation based on key."""
        if not raw_value or not raw_value.strip():
            return None
        val = raw_value.strip()

        # Date fields
        if any(dk in fact_key for dk in [
            "start_date", "end_date", "deadline", "publication_date",
            "admit_card", "result_date", "reference_date", "exam_date"
        ]):
            if " to " in val or " - " in val:
                return cls.normalize_date_range(val)
            return cls.normalize_single_date(val)

        # Total vacancies -> clean integer string
        if fact_key == "total_vacancies":
            digits_only = re.sub(r"[^\d]", "", val)
            if digits_only:
                try:
                    num = int(digits_only)
                    if 0 < num < 1000000:
                        return str(num)
                except ValueError:
                    pass
            return val

        # Age limit -> clean standard range e.g. "18-27"
        if fact_key in ("age_limit", "age_min", "age_max"):
            m_range = re.search(r"(\d{2})\s*(?:to|-)\s*(\d{2})", val)
            if m_range:
                return f"{m_range.group(1)}-{m_range.group(2)}"
            m_single = re.search(r"\b(\d{2})\b", val)
            if m_single:
                return m_single.group(1)
            return val

        # Application fee -> clean currency representation e.g. "INR 100" or "Rs. 100"
        if fact_key == "application_fee":
            m_fee = re.search(r"(?:₹|Rs\.?|INR)\s*([0-9]+)", val)
            if m_fee:
                return f"INR {m_fee.group(1)}"
            if "nil" in val.lower() or "exempted" in val.lower() or "no fee" in val.lower():
                return "Exempted / Nil"
            return val

        return val


# Alias for convenience
DateNormalizer.normalize_date = DateNormalizer.normalize_single_date
