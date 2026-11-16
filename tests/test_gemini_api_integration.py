"""Tests for Gemini API integration, configuration, and structured extraction adapter."""

import pytest
from testkart_intelligence.config import settings
from testkart_intelligence.extraction.ai_extractor import GeminiFactExtractorAdapter
from testkart_intelligence.extraction.fact_extractor import FactExtractor, ExtractedFactItem


def test_gemini_adapter_configuration():
    """Verify Gemini API adapter initialization and configuration loading."""
    adapter = GeminiFactExtractorAdapter()
    assert adapter.is_available() is True
    assert adapter.api_key == settings.GEMINI_API_KEY
    assert adapter.model == settings.GEMINI_MODEL


def test_gemini_adapter_header_and_model_resolution():
    """Verify adapter uses correct headers and fallback models."""
    adapter = GeminiFactExtractorAdapter(api_key="test-key-12345", model="gemini-3.5-flash")
    assert adapter.api_key == "test-key-12345"
    assert adapter.model == "gemini-3.5-flash"
    assert adapter.is_available() is True


def test_gemini_adapter_graceful_handling_empty_text():
    """Verify adapter gracefully returns empty list for short or empty text without errors."""
    adapter = GeminiFactExtractorAdapter()
    result = adapter.extract_facts(
        full_text="",
        authority_name="Test Authority",
        notice_title="Test Notice",
    )
    assert result == []


def test_layer_4_ai_integration_in_fact_extractor():
    """Verify FactExtractor gracefully integrates Layer 4 AI extraction."""
    pages = [
        {
            "page_number": 1,
            "text": "STAFF SELECTION COMMISSION\nCombined Higher Secondary Level Examination 2026\nDates for submission of online applications: 01.07.2026 to 31.07.2026\nTotal Vacancies: 3712 posts",
        }
    ]
    facts = FactExtractor.extract_from_pages(
        pages=pages,
        authority_name="Staff Selection Commission",
        notice_title="CHSL Examination 2026",
        official_url="https://ssc.gov.in/chsl.pdf",
    )
    keys = {f.key for f in facts}
    assert "recruiting_authority" in keys
    assert "application_start_date" in keys
    assert "application_end_date" in keys
    assert "total_vacancies" in keys
