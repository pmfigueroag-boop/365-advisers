"""
src/data/external/contracts/economic_indicator.py
──────────────────────────────────────────────────────────────────────────────
Canonical contracts for economic indicators from FRED, World Bank, IMF.

Extends the existing MacroIndicator model with richer metadata for
multi-source macro intelligence.

Consumed by:
  - Regime Weights Engine
  - Macro Dashboard
  - Alpha Signals (macro category)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class EconomicSeries(BaseModel):
    """Time series of a single economic indicator."""
    series_id: str                         # "GDP", "CPIAUCSL", "UNRATE"
    name: str = ""
    description: str = ""
    unit: str = ""                         # "Percent", "Billions of Dollars"
    frequency: str = ""                    # "monthly", "quarterly", "annual"
    seasonal_adjustment: str = ""          # "SA", "NSA"
    country: str = "US"
    source_agency: str = ""                # "BLS", "BEA", "Census", "World Bank"


class EconomicObservation(BaseModel):
    """Single data point for an economic indicator."""
    date: str                              # "2025-12-01"
    value: float
    previous: float | None = None
    change: float | None = None
    change_pct: float | None = None


class EconomicIndicatorData(BaseModel):
    """
    Complete economic indicator data from multi-source macro providers.

    Stores both series metadata and recent observations.
    """
    series: EconomicSeries
    observations: list[EconomicObservation] = Field(default_factory=list)
    latest_value: float | None = None
    latest_date: str = ""

    # Analytics
    z_score_5y: float | None = None               # vs 5-year distribution
    percentile_10y: float | None = None            # 0–100 percentile rank
    regime_signal: str = "neutral"                  # expansionary / contractionary / neutral

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, series_id: str = "UNKNOWN") -> EconomicIndicatorData:
        return cls(
            series=EconomicSeries(series_id=series_id),
            source="null",
        )
