"""Tests reproducing multi-stage exam-date extraction and age-limit edge cases."""

import pytest
from testkart_intelligence.extraction.fact_extractor import FactExtractor
from testkart_intelligence.extraction.table_extractor import TableExtractor, TableExtractionResult


def test_reproduce_multiline_exam_date_patterns():
    """Verify that multi-line exam date announcements (e.g. TNPSC CBT/OMR schedules) are captured."""
    # Test case 1: "Date of Written Examination" followed by Paper-I and date
    page_text_1 = """
4. IMPORTANT DATES AND TIME:-
Date of Notification: 12.04.2023
Last date for submission of online application: 11.05.2023
Date of Written Examination
Paper – I(Subject Paper)
(Specified topics as mentioned in the Scheme)(Degree Standard)
01.07.2023 F.N.
09.30 A.M. to 12.30 P.M.
Paper – II
01.07.2023 A.N.
02.00 P.M. to 05.00 P.M.
"""
    pages_1 = [{"page_number": 3, "text": page_text_1}]
    facts_1 = FactExtractor.extract_from_pages(
        pages_1,
        "Tamil Nadu Public Service Commission",
        "Test Notice 1",
        official_url="https://tnpsc.gov.in/test1.pdf",
    )
    exam_dates_1 = [f for f in facts_1 if f.key == "exam_date"]
    assert len(exam_dates_1) == 1, "Should extract exam date from multi-line written examination schedule"
    assert "01.07.2023" in exam_dates_1[0].value

    # Test case 2: "DATE OF EXAMINATION (COMPUTER BASED TEST)"
    page_text_2 = """
3. IMPORTANT DATES AND TIME:
Date of Notification: 18.07.2023
Last date for submission of online application: 16.08.2023
DATE OF EXAMINATION (COMPUTER BASED TEST)
PAPER –I: (Subject Paper) (Diploma Standard)
05.10.2023
09.30 A.M. to 11.00 P.M.
PAPER – II:
05.10.2023
"""
    pages_2 = [{"page_number": 2, "text": page_text_2}]
    facts_2 = FactExtractor.extract_from_pages(
        pages_2,
        "Tamil Nadu Public Service Commission",
        "Test Notice 2",
        official_url="https://tnpsc.gov.in/test2.pdf",
    )
    exam_dates_2 = [f for f in facts_2 if f.key == "exam_date"]
    assert len(exam_dates_2) == 1, "Should extract exam date from CBT multi-line schedule"
    assert "05.10.2023" in exam_dates_2[0].value

    # Test case 3: "Date and Time of Written Examination (Descriptive Type)"
    page_text_3 = """
4. IMPORTANT DATES AND TIME:
Date of Notification: 25.01.2023
Date and Time of Written Examination (Descriptive Type)
Tourist Officer in Tamil Nadu General Service
Paper – I
Tamil Eligibility Test
10.06.2023 FN
9.30 A.M. to 12.30 P.M.
"""
    pages_3 = [{"page_number": 2, "text": page_text_3}]
    facts_3 = FactExtractor.extract_from_pages(
        pages_3,
        "Tamil Nadu Public Service Commission",
        "Test Notice 3",
        official_url="https://tnpsc.gov.in/test3.pdf",
    )
    exam_dates_3 = [f for f in facts_3 if f.key == "exam_date"]
    assert len(exam_dates_3) == 1, "Should extract exam date from descriptive written examination header"
    assert "10.06.2023" in exam_dates_3[0].value


def test_reproduce_age_limit_below_years():
    """Verify that contractual notices with 'below XX years' or 'not exceeding XX years' are captured."""
    page_text = """
ENGAGEMENT OF GENERAL MANAGER ON CONTRACT BASIS
1. Name of the Post: General Manager (Testing & Assessment)
2. Number of Posts: 01
3. Age Limit: Below 58 years as on the closing date of application.
4. Educational Qualification: Master's degree in Psychology or Statistics.
"""
    pages = [{"page_number": 1, "text": page_text}]
    facts = FactExtractor.extract_from_pages(
        pages,
        "National Testing Agency",
        "Test Notice NTA GM",
        official_url="https://nta.ac.in/testgm.pdf",
    )
    age_facts = [f for f in facts if f.key == "age_limit"]
    assert len(age_facts) == 1, "Should extract age limit phrased as 'Below XX years'"
    assert "58" in age_facts[0].value
