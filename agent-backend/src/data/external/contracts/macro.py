"""
src/data/external/contracts/macro.py
──────────────────────────────────────────────────────────────────────────────
Normalized contracts for macro nowcasting data.

Captures yield curve, economic indicators, financial conditions, and
regime classification for the Regime Weights Engine, Risk & Macro agent,
and Alpha Signals.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class YieldCurve(BaseModel):
    """US Treasury yield curve snapshot."""
    date: str = ""
    us_2y: float | None = None
    us_10y: float | None = None
    us_30y: float | None = None
    spread_2s10s: float | None = None
    is_inverted: bool = False


class MacroIndicator(BaseModel):
    """Single macro-economic indicator reading."""
    name: str
    value: float
    previous: float | None = None
    change: float | None = None
    z_score: float | None = None           # vs 5-year distribution
    regime_signal: str = "neutral"         # expansionary / contractionary / neutral


class MacroContext(BaseModel):
    """
    Complete macro nowcasting snapshot.

    Consumed by:
      - RegimeWeightsEngine (regime classification)
      - Fundamental Engine (Risk & Macro agent context)
      - Alpha Signals (macro category)
      - Decision Engine (CIO Memo context)
    """
    as_of: str = ""
    yield_curve: YieldCurve | None = None
    vix: float | None = None
    vix_term_structure: str = "normal"      # contango / backwardation / flat
    fed_funds_rate: float | None = None
    cpi_yoy: float | None = None
    pce_yoy: float | None = None
    unemployment_rate: float | None = None
    ism_manufacturing: float | None = None
    financial_conditions_index: float | None = None
    indicators: list[MacroIndicator] = Field(default_factory=list)
    regime_classification: str = "unknown"  # risk_on / risk_off / transition

    # Extended FRED series (Phase 2)
    gdp_growth_annualized: float | None = None
    nonfarm_payrolls_change: float | None = None
    retail_sales_mom: float | None = None
    housing_starts: float | None = None
    consumer_confidence: float | None = None
    leading_indicators_index: float | None = None

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)

    @classmethod
    def default(cls) -> MacroContext:
        """Neutral default — all engines continue with existing heuristics."""
        return cls(source="null", regime_classification="unknown")
