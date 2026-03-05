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

    # ── External API resilience
    YFINANCE_TIMEOUT: int = 15          # seconds
    YFINANCE_MAX_RETRIES: int = 2
    YFINANCE_RETRY_DELAY: float = 1.0   # seconds

    # ── Database
    DB_PATH: str = ""  # Resolved at runtime if empty

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
