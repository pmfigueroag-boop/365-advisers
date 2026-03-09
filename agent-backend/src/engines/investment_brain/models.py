"""
src/engines/investment_brain/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the Investment Brain — Financial Decision Intelligence.

Covers: Market Regime, Opportunities, Portfolio Suggestions, Risk Alerts,
        Investment Insights, and the master Dashboard output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Market Regime ────────────────────────────────────────────────────────────

class MarketRegime(str, Enum):
    EXPANSION = "expansion"
    SLOWDOWN = "slowdown"
    RECESSION = "recession"
    RECOVERY = "recovery"
    HIGH_VOLATILITY = "high_volatility"
    LIQUIDITY_EXPANSION = "liquidity_expansion"


class RegimeFactor(BaseModel):
    """One factor contributing to the regime classification."""
    name: str
    value: float | None = None
    signal: str = "neutral"  # bullish / bearish / neutral
    weight: float = 0.0
    description: str = ""


class RegimeClassification(BaseModel):
    """Full market regime detection result."""
    regime: MarketRegime = MarketRegime.EXPANSION
    confidence: float = Field(0.5, ge=0, le=1.0)
    probabilities: dict[str, float] = Field(default_factory=dict)
    contributing_factors: list[RegimeFactor] = Field(default_factory=list)
    summary: str = ""
    previous_regime: MarketRegime | None = None
    regime_changed: bool = False
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Opportunity Detection ────────────────────────────────────────────────────

class OpportunityType(str, Enum):
    UNDERVALUED = "undervalued"
    MOMENTUM_BREAKOUT = "momentum_breakout"
    SENTIMENT_DRIVEN = "sentiment_driven"
    MACRO_ALIGNED = "macro_aligned"
    EVENT_CATALYST = "event_catalyst"


class DetectedOpportunity(BaseModel):
    """A single actionable investment opportunity."""
    ticker: str
    opportunity_type: OpportunityType
    alpha_score: float = Field(0.0, ge=0, le=100)
    confidence: float = Field(0.5, ge=0, le=1.0)
    signals: list[str] = Field(default_factory=list)
    justification: str = ""
    regime_alignment: str = ""
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Portfolio Advisory ───────────────────────────────────────────────────────

class PortfolioStyle(str, Enum):
    GROWTH = "growth"
    VALUE = "value"
    INCOME = "income"
    DEFENSIVE = "defensive"
    OPPORTUNISTIC = "opportunistic"


class SuggestedPosition(BaseModel):
    """One position within a suggested portfolio."""
    ticker: str
    weight: float = Field(0.0, ge=0, le=1.0)
    justification: str = ""
    factor_exposures: dict[str, float] = Field(default_factory=dict)


class PortfolioSuggestion(BaseModel):
    """A complete portfolio suggestion for one investment style."""
    style: PortfolioStyle
    positions: list[SuggestedPosition] = Field(default_factory=list)
    rationale: str = ""
    expected_return_profile: str = ""
    risk_level: str = "moderate"
    regime_suitability: str = ""


# ── Risk Detection ───────────────────────────────────────────────────────────

class RiskAlertSeverity(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAlertType(str, Enum):
    BUBBLE_SIGNAL = "bubble_signal"
    SYSTEMIC_RISK = "systemic_risk"
    SECTOR_OVERHEATING = "sector_overheating"
    LIQUIDITY_STRESS = "liquidity_stress"
    DRAWDOWN_WARNING = "drawdown_warning"
    CORRELATION_SPIKE = "correlation_spike"


class RiskAlert(BaseModel):
    """A single risk alert with full traceability."""
    alert_type: RiskAlertType
    severity: RiskAlertSeverity = RiskAlertSeverity.MODERATE
    title: str = ""
    description: str = ""
    affected_tickers: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    source_signals: list[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Investment Insights ──────────────────────────────────────────────────────

class InsightCategory(str, Enum):
    REGIME = "regime"
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    SENTIMENT = "sentiment"
    MACRO = "macro"


class InvestmentInsight(BaseModel):
    """Human-readable insight with what/why/implication structure."""
    what_happened: str
    why_it_happened: str
    what_it_means: str
    category: InsightCategory = InsightCategory.REGIME
    confidence: float = Field(0.5, ge=0, le=1.0)
    related_tickers: list[str] = Field(default_factory=list)
    factors_used: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Alerts ───────────────────────────────────────────────────────────────────

class BrainAlertType(str, Enum):
    REGIME_CHANGE = "regime_change"
    NEW_OPPORTUNITY = "new_opportunity"
    NEW_RISK = "new_risk"
    TOP_ALPHA_ENTRY = "top_alpha_entry"


class BrainAlert(BaseModel):
    """Alert generated when the brain detects a significant change."""
    alert_type: BrainAlertType
    severity: RiskAlertSeverity = RiskAlertSeverity.MODERATE
    title: str
    description: str
    related_tickers: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Master Dashboard ─────────────────────────────────────────────────────────

class InvestmentBrainDashboard(BaseModel):
    """Complete output of the Investment Brain analysis."""
    regime: RegimeClassification
    opportunities: list[DetectedOpportunity] = Field(default_factory=list)
    portfolios: list[PortfolioSuggestion] = Field(default_factory=list)
    risk_alerts: list[RiskAlert] = Field(default_factory=list)
    insights: list[InvestmentInsight] = Field(default_factory=list)
    alerts: list[BrainAlert] = Field(default_factory=list)
    asset_count: int = 0
    analysis_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
