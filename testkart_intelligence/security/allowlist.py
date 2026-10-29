"""Official Government Domain Verification and Allowlist Enforcement.

Policy:
- Official government recruitment websites and designated portals must be the
  authoritative evidence for recruitment information.
- Never accept search snippets, blogs, social media posts, coaching websites,
  or news websites as authoritative evidence.
- Lookalikes, unauthorized commercial TLDs (.com, .org, .net), and unverified domains
  are strictly rejected.
"""

import ipaddress
import re
from typing import Set, Tuple
from urllib.parse import urlparse


# Standard official government domain suffixes in India
OFFICIAL_GOV_SUFFIXES: Tuple[str, ...] = (
    ".gov.in",
    ".nic.in",
)

# Explicitly verified non-standard official portal domains (e.g. IBPS, NTA, High Courts)
VERIFIED_OFFICIAL_EXPLICIT_DOMAINS: Set[str] = {
    "ibps.in",                # Institute of Banking Personnel Selection
    "nta.ac.in",              # National Testing Agency
    "indianrailways.gov.in",  # Ministry of Railways
    "rrbcdg.gov.in",          # Railway Recruitment Board Chandigarh (and other RRBs)
    "allahabadhighcourt.in",  # Allahabad High Court
    "sci.gov.in",             # Supreme Court of India
    "joinindianarmy.nic.in",  # Indian Army
    "joinindiannavy.gov.in",  # Indian Navy
    "careerindianairforce.cdac.in", # Indian Air Force via CDAC
}

# Known untrusted coaching, job scraper, aggregator, or lookalike patterns
PROHIBITED_DOMAIN_PATTERNS = [
    r"sarkari",
    r"freejobalert",
    r"jagranjosh",
    r"testbook",
    r"adda247",
    r"careerpower",
    r"freshersworld",
    r"indgovtjobs",
    r"shiksha",
    r"unacademy",
    r"byjus",
    r"facebook",
    r"twitter",
    r"t\.me",
    r"youtube",
    r"instagram",
    r"linkedin",
    r"quora",
    r"blogspot",
    r"wordpress",
]


class SecurityValidationError(ValueError):
    """Raised when a URL violates official domain security policies."""
    pass


def extract_domain(url: str) -> str:
    """Extract and normalize host domain from URL safely, rejecting embedded credentials and malformed hosts."""
    if not url or not isinstance(url, str):
        raise SecurityValidationError("Empty URL provided")

    parsed = urlparse(url.strip())
    if not parsed.scheme or parsed.scheme.lower() not in ("http", "https"):
        raise SecurityValidationError(f"Invalid URL scheme '{parsed.scheme}': must be http or https")

    # Reject embedded userinfo (e.g. https://upsc.gov.in@attacker.com)
    if parsed.username or parsed.password:
        raise SecurityValidationError("URLs with embedded userinfo (credentials) are prohibited")

    hostname = parsed.hostname
    if not hostname:
        raise SecurityValidationError("URL has no valid hostname")

    return hostname.lower().strip()


def is_official_domain(domain_or_url: str) -> bool:
    """Determine whether a given domain or URL is a verified official government domain."""
    try:
        domain = extract_domain(domain_or_url) if "://" in domain_or_url else domain_or_url.lower().strip()
    except Exception:
        return False

    if not domain:
        return False

    # Disallow localhost
    if domain in ("localhost", "localhost.localdomain"):
        return False

    # Disallow all IP addresses (IPv4 & IPv6, loopback, private, link-local, public)
    try:
        ipaddress.ip_address(domain)
        return False
    except ValueError:
        pass

    # Check against known predatory/lookalike keyword patterns
    for pat in PROHIBITED_DOMAIN_PATTERNS:
        if re.search(pat, domain):
            return False

    # Check verified explicit domains (e.g. ibps.in, nta.ac.in)
    if domain in VERIFIED_OFFICIAL_EXPLICIT_DOMAINS:
        return True

    # Check subdomain of explicit allowlist
    for explicit in VERIFIED_OFFICIAL_EXPLICIT_DOMAINS:
        if domain.endswith("." + explicit):
            return True

    # Check official government suffixes (.gov.in, .nic.in)
    for suffix in OFFICIAL_GOV_SUFFIXES:
        if domain.endswith(suffix):
            # Ensure proper domain boundary (e.g. evil-gov.in is rejected because suffix starts with .)
            return True

    return False


def validate_official_url(url: str) -> str:
    """Validate that a URL is well-formed, uses HTTPS/HTTP, and targets an official domain.

    Returns the clean URL or raises SecurityValidationError.
    """
    if not url or not isinstance(url, str):
        raise SecurityValidationError("URL must be a non-empty string")

    parsed = urlparse(url.strip())
    if not parsed.scheme or parsed.scheme.lower() not in ("http", "https"):
        raise SecurityValidationError(f"Disallowed scheme '{parsed.scheme}'. Only HTTP/HTTPS allowed.")

    domain = extract_domain(url)

    # Lookalike attack checks (e.g. upsc.gov.in.scam.com or upsc-gov.in)
    if not is_official_domain(domain):
        raise SecurityValidationError(
            f"Domain '{domain}' is not an authorized official government portal. "
            f"Commercial domains, scraping blogs, and unverified third parties are strictly rejected."
        )

    return url.strip()


def validate_redirect_chain(start_url: str, redirect_urls: list[str]) -> bool:
    """Validate that every step in a redirect chain satisfies official domain policies."""
    validate_official_url(start_url)
    for r_url in redirect_urls:
        validate_official_url(r_url)
    return True
