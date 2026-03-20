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
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    LOG_LEVEL: str = "INFO"

    # ── LLM
    LLM_MODEL: str = "gemini-2.5-pro"              # Legacy alias (= REASONING)
    LLM_REASONING_MODEL: str = "gemini-2.5-pro"    # Deep analysis, CIO memos
    LLM_FAST_MODEL: str = "gemini-2.5-flash"       # Agent memos, extraction
    LLM_FALLBACK_ENABLED: bool = True              # Auto-fallback to secondary LLM
    LLM_FALLBACK_MODEL: str = "gpt-4o-mini"        # OpenAI fallback model
    OPENAI_API_KEY: str = ""                        # Empty = fallback disabled

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

    # ── New provider keys (multi-source integration layer) ────────────────
    ALPHA_VANTAGE_API_KEY: str = ""
    TWELVE_DATA_API_KEY: str = ""
    FMP_API_KEY: str = ""
    STOCKTWITS_API_KEY: str = ""          # optional for higher rate limit
    SANTIMENT_API_KEY: str = ""
    SIMILARWEB_API_KEY: str = ""          # commercial — stub only
    THINKNUM_API_KEY: str = ""            # commercial — stub only
    CBOE_API_KEY: str = ""                # public data, key optional
    OPTIONMETRICS_API_KEY: str = ""       # commercial — stub only

    # Provider timeouts (seconds)
    EDPL_DEFAULT_TIMEOUT: int = 10
    EDPL_POLYGON_TIMEOUT: int = 10
    EDPL_NEWS_TIMEOUT: int = 8
    EDPL_FRED_TIMEOUT: int = 8
    EDPL_FINNHUB_TIMEOUT: int = 10
    EDPL_QUIVER_TIMEOUT: int = 12
    EDPL_EDGAR_TIMEOUT: int = 15
    EDPL_GDELT_TIMEOUT: int = 20
    # New provider timeouts
    EDPL_AV_TIMEOUT: int = 12             # Alpha Vantage
    EDPL_TD_TIMEOUT: int = 10             # Twelve Data
    EDPL_FMP_TIMEOUT: int = 10            # Financial Modeling Prep
    EDPL_WB_TIMEOUT: int = 15             # World Bank
    EDPL_ST_TIMEOUT: int = 8              # Stocktwits
    EDPL_SAN_TIMEOUT: int = 10            # Santiment
    EDPL_IMF_TIMEOUT: int = 15            # IMF
    EDPL_CBOE_TIMEOUT: int = 10           # Cboe

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
    EDPL_CACHE_TTL_FUNDAMENTAL: int = 86400    # 24 hours
    EDPL_CACHE_TTL_ALTERNATIVE: int = 86400    # 24 hours
    EDPL_CACHE_TTL_VOLATILITY: int = 900       # 15 min

    # Feature flags — enable/disable entire data domains
    EDPL_ENABLE_MARKET_DATA: bool = True
    EDPL_ENABLE_ETF_FLOWS: bool = True
    EDPL_ENABLE_OPTIONS: bool = True
    EDPL_ENABLE_INSTITUTIONAL: bool = True
    EDPL_ENABLE_SENTIMENT: bool = True
    EDPL_ENABLE_MACRO: bool = True
    EDPL_ENABLE_FILING_EVENTS: bool = True
    EDPL_ENABLE_GEOPOLITICAL: bool = True
    EDPL_ENABLE_FUNDAMENTAL: bool = True
    EDPL_ENABLE_ALTERNATIVE: bool = True
    EDPL_ENABLE_VOLATILITY: bool = True

    # ── Authentication & Authorization ─────────────────────────────────
    AUTH_ENABLED: bool = False                     # Set True to enforce JWT auth
    JWT_SECRET_KEY: str = "365-advisers-dev-secret-CHANGE-IN-PRODUCTION"
    JWT_EXPIRATION_MINUTES: int = 480              # 8 hours
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = "$2b$12$oWydfZyOI4zn0SdQxebEVe9KCgbOR/R3EV4S1mHfohysI3nXqb3qC"  # bcrypt("admin")
    ANALYST_PASSWORD_HASH: str = "$2b$12$mUkSDn7.ngJypoLYm0VNveW.Z/XmfUao1DK3DJlOZyYhRKM/eVhR."  # bcrypt("analyst")
    VIEWER_PASSWORD_HASH: str = "$2b$12$MEy8jtiPKy3xiaH7HP3qVePlMtlUwp9lHbGWwW5jIj/l.c2j3pGYi"  # bcrypt("viewer")

    # ── Observability ─────────────────────────────────────────────────────
    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "365-advisers-api"
    OTEL_EXPORTER: str = "console"                 # "console" | "otlp"
    OTEL_ENDPOINT: str = "http://localhost:4318"    # OTLP HTTP endpoint

    # ── Cache & Redis ──────────────────────────────────────────────────────
    CACHE_BACKEND: str = "memory"                  # "memory" | "redis"
    REDIS_URL: str = "redis://localhost:6379/0"
    PROMPT_CACHE_ENABLED: bool = True              # Gemini system instruction caching

    # ── Database
    DATABASE_URL: str = "sqlite:///advisers.db"  # Override with postgresql+psycopg://... in .env

    # ── Performance
    UVICORN_WORKERS: int = 1                       # Override to 4+ in docker/production

    model_config = {"env_file": ".env", "extra": "ignore"}


_DEFAULT_JWT_SECRET = "365-advisers-dev-secret-CHANGE-IN-PRODUCTION"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    # ── JWT Secret Guard ──────────────────────────────────────────────────
    if settings.JWT_SECRET_KEY == _DEFAULT_JWT_SECRET:
        if settings.AUTH_ENABLED:
            raise RuntimeError(
                "SECURITY ERROR: JWT_SECRET_KEY is set to the default value "
                "while AUTH_ENABLED=True. Set a strong, unique secret in .env "
                "or environment before enabling authentication."
            )
        else:
            import logging
            logging.getLogger("365advisers.config").warning(
                "JWT_SECRET_KEY is using the default dev value. "
                "Set a strong secret before enabling AUTH_ENABLED=True."
            )
    return settings
