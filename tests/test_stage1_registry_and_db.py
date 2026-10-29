"""Unit tests for Stage 1: Security Allowlist, Database schema, and Source Registry."""

import pytest
import sqlite3
from pathlib import Path
from testkart_intelligence.database.connection import get_db, init_db
from testkart_intelligence.registry.service import SourceRegistryService, seed_sources_if_empty
from testkart_intelligence.security.allowlist import (
    is_official_domain,
    validate_official_url,
    validate_redirect_chain,
    SecurityValidationError,
)


@pytest.fixture
def test_db(tmp_path: Path):
    """Fixture providing a temporary database."""
    db_file = tmp_path / "test_testkart.db"
    init_db(db_file)
    with get_db(db_file) as conn:
        seed_sources_if_empty(conn)
    return db_file


def test_official_domain_allowlist():
    """Verify that legitimate official domains pass and lookalikes/scams are rejected."""
    # Legitimate government domains
    assert is_official_domain("upsc.gov.in") is True
    assert is_official_domain("ssc.gov.in") is True
    assert is_official_domain("bpsc.bih.nic.in") is True
    assert is_official_domain("kpsc.kar.nic.in") is True
    assert is_official_domain("ibps.in") is True
    assert is_official_domain("nta.ac.in") is True
    assert is_official_domain("https://upsc.gov.in/notices") is True

    # Lookalike, predatory, aggregator, and commercial domains
    assert is_official_domain("upsc-gov.in") is False
    assert is_official_domain("upsc.com") is False
    assert is_official_domain("sarkariresult.com") is False
    assert is_official_domain("freejobalert.com") is False
    assert is_official_domain("testbook.com") is False
    assert is_official_domain("adda247.com") is False
    assert is_official_domain("fake-upsc.gov.in.evil.com") is False
    assert is_official_domain("localhost") is False
    assert is_official_domain("127.0.0.1") is False


def test_validate_official_url_enforcement():
    """Verify that URL validation strictly enforces official domains."""
    valid_url = "https://upsc.gov.in/examinations/active-examinations"
    assert validate_official_url(valid_url) == valid_url

    # Disallow invalid schemes
    with pytest.raises(SecurityValidationError, match="Disallowed scheme"):
        validate_official_url("ftp://upsc.gov.in/test.pdf")

    # Disallow commercial / unauthorized domains
    with pytest.raises(SecurityValidationError, match="not an authorized official government portal"):
        validate_official_url("https://sarkariresult.com/upsc-notification")


def test_validate_redirect_chain():
    """Ensure redirect chain validation rejects redirect to unofficial domain."""
    valid_chain = [
        "https://upsc.gov.in/examinations",
        "https://upsc.gov.in/examinations/active",
    ]
    assert validate_redirect_chain("https://upsc.gov.in", valid_chain) is True

    bad_chain = [
        "https://upsc.gov.in/examinations",
        "https://sarkariresult.com/fake-redirect",
    ]
    with pytest.raises(SecurityValidationError):
        validate_redirect_chain("https://upsc.gov.in", bad_chain)


def test_database_initialization_and_seeding(test_db: Path):
    """Verify tables are created and seeded with official sources."""
    service = SourceRegistryService(test_db)
    sources = service.list_sources()
    assert len(sources) >= 10

    # Check key seeded agencies
    codes = {s["code"] for s in sources}
    assert "UPSC" in codes
    assert "SSC" in codes
    assert "IBPS" in codes
    assert "RRB_CHD" in codes
    assert "BPSC" in codes
    assert "UPPSC" in codes


def test_register_new_source(test_db: Path):
    """Test registering a new verified official government source."""
    service = SourceRegistryService(test_db)

    # Valid official portal
    new_src = service.register_source(
        code="OPSC",
        name="Odisha Public Service Commission",
        category="PSC",
        state="Odisha",
        listing_url="https://opsc.gov.in/notices.html",
    )
    assert new_src is not None
    assert new_src["code"] == "OPSC"
    assert new_src["official_domain"] == "opsc.gov.in"

    # Reject non-official portal
    with pytest.raises(SecurityValidationError):
        service.register_source(
            code="FAKESRC",
            name="Fake Jobs Blog",
            category="Central",
            state="Central",
            listing_url="https://sarkarijobsalert.com/notices",
        )


def test_enable_disable_source(test_db: Path):
    """Test toggle enabled/disabled status of a source."""
    service = SourceRegistryService(test_db)
    assert service.set_enabled("UPSC", False) is True

    upsc = service.get_source_by_code("UPSC")
    assert upsc["enabled"] == 0

    enabled_sources = service.list_sources(enabled_only=True)
    assert "UPSC" not in {s["code"] for s in enabled_sources}

    service.set_enabled("UPSC", True)
    upsc_updated = service.get_source_by_code("UPSC")
    assert upsc_updated["enabled"] == 1
