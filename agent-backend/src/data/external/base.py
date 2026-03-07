"""
src/data/external/base.py
──────────────────────────────────────────────────────────────────────────────
Foundation types for the External Data Provider Layer.

Defines the abstract ProviderAdapter contract that every external data source
adapter must implement, plus shared enumerations and request/response models.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.external.base")


# ─── Enumerations ─────────────────────────────────────────────────────────────


class DataDomain(str, Enum):
    """Logical domains of external data."""
    MARKET_DATA = "market_data"
    ETF_FLOWS = "etf_flows"
    OPTIONS = "options"
    INSTITUTIONAL = "institutional"
    SENTIMENT = "sentiment"
    MACRO = "macro"
    FILING_EVENTS = "filing_events"
    GEOPOLITICAL = "geopolitical"


class ProviderStatus(str, Enum):
    """Runtime health status of a provider."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    UNKNOWN = "unknown"
    STALE = "stale"


class ProviderCapability(str, Enum):
    """Fine-grained capabilities a provider can expose."""
    # Market Data
    INTRADAY_BARS = "intraday_bars"
    DAILY_BARS = "daily_bars"
    LIQUIDITY_METRICS = "liquidity_metrics"
    TRADES_QUOTES = "trades_quotes"

    # ETF Flows
    SECTOR_FLOWS = "sector_flows"
    FACTOR_FLOWS = "factor_flows"
    THEMATIC_FLOWS = "thematic_flows"

    # Options
    IMPLIED_VOLATILITY = "implied_volatility"
    OPTIONS_CHAIN = "options_chain"
    UNUSUAL_ACTIVITY = "unusual_activity"
    GAMMA_EXPOSURE = "gamma_exposure"

    # Institutional
    INSIDER_TRANSACTIONS = "insider_transactions"
    OWNERSHIP_CHANGES = "ownership_changes"

    # Sentiment
    NEWS_HEADLINES = "news_headlines"
    SENTIMENT_SCORES = "sentiment_scores"
    CATALYST_DETECTION = "catalyst_detection"

    # Macro
    YIELD_CURVE = "yield_curve"
    ECONOMIC_INDICATORS = "economic_indicators"
    FINANCIAL_CONDITIONS = "financial_conditions"

    # Institutional Intelligence (Quiver / Finnhub)
    CONGRESSIONAL_TRADES = "congressional_trades"
    LOBBYING_DATA = "lobbying_data"
    GOV_CONTRACTS = "gov_contracts"
    EARNINGS_SURPRISES = "earnings_surprises"

    # Filing Events (SEC EDGAR)
    SEC_FILINGS = "sec_filings"
    MATERIAL_EVENTS = "material_events"
    OWNERSHIP_FILINGS = "ownership_filings"

    # Geopolitical (GDELT)
    GEOPOLITICAL_EVENTS = "geopolitical_events"
    GEOPOLITICAL_TONE = "geopolitical_tone"
    COUNTRY_RISK = "country_risk"


# ─── Request / Response Models ────────────────────────────────────────────────


class ProviderRequest(BaseModel):
    """Standardised request passed to any adapter."""
    domain: DataDomain
    ticker: str | None = None          # None for macro/global requests
    params: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProviderResponse(BaseModel):
    """Standardised wrapper for adapter responses."""
    domain: DataDomain
    provider_name: str
    status: ProviderStatus = ProviderStatus.ACTIVE
    data: Any = None                   # typed contract object
    cached: bool = False
    latency_ms: float = 0.0
    error: str | None = None
    responded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def ok(self) -> bool:
        return self.error is None and self.data is not None


class HealthStatus(BaseModel):
    """Health-check result for a single provider."""
    provider_name: str
    domain: DataDomain
    status: ProviderStatus = ProviderStatus.UNKNOWN
    last_success: datetime | None = None
    last_failure: datetime | None = None
    consecutive_failures: int = 0
    avg_latency_ms: float = 0.0
    message: str = ""


# ─── Abstract Adapter ─────────────────────────────────────────────────────────


class ProviderAdapter(ABC):
    """
    Abstract base class for all external data adapters.

    Each concrete adapter wraps a single external API and converts its raw
    output into a normalised Pydantic contract.  The adapter owns:
      - Authentication & rate-limit management
      - Timeout + retry with backoff
      - Transformation to the normalised contract
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name (e.g. 'polygon', 'fred')."""
        ...

    @property
    @abstractmethod
    def domain(self) -> DataDomain:
        """The data domain this adapter serves."""
        ...

    @abstractmethod
    def get_capabilities(self) -> set[ProviderCapability]:
        """Return the fine-grained capabilities this adapter supports."""
        ...

    @abstractmethod
    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """
        Execute a data fetch and return a typed ProviderResponse.

        Implementations MUST:
          - Catch all exceptions and return an error ProviderResponse
          - Record latency in ``ProviderResponse.latency_ms``
          - Return ``ProviderResponse(status=DEGRADED, ...)`` on partial data
        """
        ...

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """
        Lightweight probe to verify the provider is reachable.

        Should NOT fetch real data — just validate connectivity / auth.
        """
        ...

    # ── Convenience helpers ──────────────────────────────────────────────

    def _ok_response(
        self,
        data: Any,
        latency_ms: float = 0.0,
        cached: bool = False,
    ) -> ProviderResponse:
        """Build a successful response."""
        return ProviderResponse(
            domain=self.domain,
            provider_name=self.name,
            status=ProviderStatus.ACTIVE,
            data=data,
            cached=cached,
            latency_ms=latency_ms,
        )

    def _error_response(
        self,
        error: str,
        latency_ms: float = 0.0,
    ) -> ProviderResponse:
        """Build an error response."""
        return ProviderResponse(
            domain=self.domain,
            provider_name=self.name,
            status=ProviderStatus.DEGRADED,
            error=error,
            latency_ms=latency_ms,
        )
