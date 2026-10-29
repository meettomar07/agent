"""Live Publishing Safety Guard.

Enforces that live publishing to CMS, websites, or external APIs remains strictly
disabled during the local development phase.
"""

from testkart_intelligence.config import settings


class LivePublishingDisabledError(PermissionError):
    """Raised when an attempt is made to trigger live website publishing."""
    pass


def assert_live_publishing_disabled() -> None:
    """Ensure live publishing cannot be invoked."""
    if settings.ALLOW_LIVE_PUBLISHING:
        raise LivePublishingDisabledError(
            "CRITICAL SECURITY VIOLATION: Live website publishing is strictly disabled in this phase. "
            "Do not connect to live Testkart CMS or external publishing endpoints."
        )


def verify_can_publish_mock() -> bool:
    """Verify that only mock publishing is permitted."""
    assert_live_publishing_disabled()
    return True
