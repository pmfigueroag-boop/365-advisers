"""
src/config.py
─────────────────────────────────────────────────────────────────────────────
Centralized configuration via pydantic-settings.
Validates all required environment variables at startup.
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Required
    GOOGLE_API_KEY: str

    # ── Server
    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"

    # ── LLM
    LLM_MODEL: str = "gemini-2.5-pro"

    # ── External API resilience (legacy)
    YFINANCE_TIMEOUT: int = 15          # seconds
    YFINANCE_MAX_RETRIES: int = 2
    YFINANCE_RETRY_DELAY: float = 1.0   # seconds

    # ── EDPL: External Data Provider Layer ────────────────────────────────
    # API Keys (empty = provider disabled, system degrades gracefully)
    POLYGON_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    FRED_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""
    QUIVER_API_KEY: str = ""
    # SEC EDGAR requires no API key — only a User-Agent email
    SEC_EDGAR_EMAIL: str = ""
    # GDELT is fully open — no key needed

    # Provider timeouts (seconds)
    EDPL_DEFAULT_TIMEOUT: int = 10
    EDPL_POLYGON_TIMEOUT: int = 10
    EDPL_NEWS_TIMEOUT: int = 8
    EDPL_FRED_TIMEOUT: int = 8
    EDPL_FINNHUB_TIMEOUT: int = 10
    EDPL_QUIVER_TIMEOUT: int = 12
    EDPL_EDGAR_TIMEOUT: int = 15
    EDPL_GDELT_TIMEOUT: int = 20

    # Retry policy
    EDPL_DEFAULT_MAX_RETRIES: int = 2
    EDPL_DEFAULT_RETRY_DELAY: float = 1.0  # seconds (base for exponential backoff)

    # Circuit breaker
    EDPL_CB_FAILURE_THRESHOLD: int = 3     # failures before opening
    EDPL_CB_RECOVERY_TIMEOUT: float = 60.0 # seconds before half-open

    # Cache TTLs (seconds)
    EDPL_CACHE_TTL_MARKET: int = 900       # 15 min
    EDPL_CACHE_TTL_ETF_FLOWS: int = 3600   # 1 hour
    EDPL_CACHE_TTL_OPTIONS: int = 900      # 15 min
    EDPL_CACHE_TTL_INSTITUTIONAL: int = 86400  # 24 hours
    EDPL_CACHE_TTL_SENTIMENT: int = 1800   # 30 min
    EDPL_CACHE_TTL_MACRO: int = 21600      # 6 hours
    EDPL_CACHE_TTL_FILING_EVENTS: int = 86400  # 24 hours
    EDPL_CACHE_TTL_GEOPOLITICAL: int = 43200   # 12 hours

    # Feature flags — enable/disable entire data domains
    EDPL_ENABLE_MARKET_DATA: bool = True
    EDPL_ENABLE_ETF_FLOWS: bool = True
    EDPL_ENABLE_OPTIONS: bool = True
    EDPL_ENABLE_INSTITUTIONAL: bool = True
    EDPL_ENABLE_SENTIMENT: bool = True
    EDPL_ENABLE_MACRO: bool = True
    EDPL_ENABLE_FILING_EVENTS: bool = True
    EDPL_ENABLE_GEOPOLITICAL: bool = True

    # ── Database
    DATABASE_URL: str = "sqlite:///advisers.db"  # Override with postgresql+psycopg://... in .env

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
