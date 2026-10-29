"""Configuration and environment settings for Testkart Intelligence."""

from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="TESTKART_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DOCUMENTS_DIR: Path = DATA_DIR / "documents"
    DATABASE_PATH: Path = DATA_DIR / "testkart.db"

    # Scheduling
    TIMEZONE: str = "Asia/Kolkata"
    SCAN_HOURS: List[int] = [6, 18]  # Twice daily at 06:00 and 18:00 IST
    SCAN_MINUTES: int = 0
    ENABLE_BACKGROUND_SCHEDULER: bool = False  # Set to True for live daemon execution

    # HTTP & Crawler Settings
    REQUEST_TIMEOUT_SECONDS: float = 25.0
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 1.5
    RATE_LIMIT_DELAY_SECONDS: float = 1.0  # Polite crawl delay per host
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; Testkart-Intelligence/1.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    MAX_REDIRECTS: int = 5
    MAX_DOCUMENT_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB max per PDF

    # Security & Publishing Safety
    SERVER_HOST: str = "127.0.0.1"  # Bound strictly to localhost
    SERVER_PORT: int = 8000
    ALLOW_LIVE_PUBLISHING: bool = False  # MUST remain False during local development phase
    REQUIRE_CONTENT_HASH_VERIFICATION: bool = True
    APPROVAL_TOKEN_EXPIRY_HOURS: int = 48

    # Project Owner & Administrative Contact
    OWNER_EMAIL: str = "meettomar07@gmail.com"

    # Notification & External Messaging (STRICTLY disabled in local development)
    ENABLE_EMAIL_NOTIFICATIONS: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587

    # AI / LLM Generation
    AI_PROVIDER: str = "deterministic"  # "deterministic" | "gemini" | "mock"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Quality Assurance Thresholds
    MIN_QA_PASS_SCORE: float = 85.0
    MAX_TITLE_LENGTH: int = 120
    MIN_TITLE_LENGTH: int = 15

    def ensure_directories(self) -> None:
        """Ensure necessary data directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
