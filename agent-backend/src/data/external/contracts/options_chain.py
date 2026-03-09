"""
src/data/external/contracts/options_chain.py
──────────────────────────────────────────────────────────────────────────────
Canonical contracts for full options chain data.

Extends the existing OptionsIntelligence contract with detailed chain-level
data: individual contracts, greeks, bid/ask, volume, OI.

Consumed by:
  - Options Pricing Engine (BS-Greeks)
  - Crowding Engine (gamma exposure, unusual activity)
  - Alpha Signals (volatility category)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class OptionContract(BaseModel):
    """Single options contract in a chain."""
    contract_type: str = ""                # CALL / PUT
    strike: float = 0.0
    expiration: str = ""                   # "2025-03-21"
    last_price: float | None = None
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    volume: int = 0
    open_interest: int = 0
    implied_volatility: float | None = None

    # Greeks
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None

    # Derived
    intrinsic_value: float | None = None
    time_value: float | None = None
    vol_oi_ratio: float | None = None
    in_the_money: bool = False


class OptionsExpiration(BaseModel):
    """Options chain for a single expiration date."""
    expiration: str = ""                   # "2025-03-21"
    days_to_expiry: int = 0
    calls: list[OptionContract] = Field(default_factory=list)
    puts: list[OptionContract] = Field(default_factory=list)


class OptionsChainData(BaseModel):
    """
    Full options chain for a ticker across all expirations.

    Provides chain-level granularity for pricing, hedging, and
    flow analysis.
    """
    ticker: str
    underlying_price: float | None = None
    expirations: list[OptionsExpiration] = Field(default_factory=list)
    available_expiration_dates: list[str] = Field(default_factory=list)

    # Summary statistics
    total_call_volume: int = 0
    total_put_volume: int = 0
    total_call_oi: int = 0
    total_put_oi: int = 0
    overall_put_call_ratio: float | None = None

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> OptionsChainData:
        return cls(ticker=ticker, source="null")
