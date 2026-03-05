"""
src/engines/alpha_decay/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Alpha Decay & Signal Half-Life Model.

Defines decay configuration, decay-adjusted signal outputs, and profile-level
freshness metrics.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from src.engines.alpha_signals.models import (
    SignalCategory,
    SignalStrength,
    EvaluatedSignal,
)


# ─── Decay Function Type ─────────────────────────────────────────────────────

class DecayFunctionType(str, Enum):
    """Supported decay function shapes."""
    EXPONENTIAL = "exponential"
    LOGISTIC = "logistic"


# ─── Freshness Classification ────────────────────────────────────────────────

class FreshnessLevel(str, Enum):
    """Semantic label for signal freshness."""
    FRESH = "fresh"           # decay_factor >= 0.80
    AGING = "aging"           # 0.50 <= decay_factor < 0.80
    STALE = "stale"           # 0.20 <= decay_factor < 0.50
    EXPIRED = "expired"       # decay_factor < 0.20


# ─── Default Half-Life Configuration ─────────────────────────────────────────

DEFAULT_HALF_LIFE_DAYS: dict[str, float] = {
    SignalCategory.EVENT.value: 3.0,
    SignalCategory.FLOW.value: 5.0,
    SignalCategory.MOMENTUM.value: 10.0,
    SignalCategory.VOLATILITY.value: 14.0,
    SignalCategory.GROWTH.value: 60.0,
    SignalCategory.MACRO.value: 90.0,
    SignalCategory.QUALITY.value: 180.0,
    SignalCategory.VALUE.value: 180.0,
}

# Minimum decay factor before a signal is considered expired
DEFAULT_EXPIRATION_THRESHOLD = 0.05


# ─── Decay Configuration ─────────────────────────────────────────────────────

class DecayConfig(BaseModel):
    """Global configuration for the decay engine."""
    half_life_days: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_HALF_LIFE_DAYS),
        description="Half-life in days per signal category",
    )
    expiration_threshold: float = Field(
        DEFAULT_EXPIRATION_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Decay factor below which a signal is considered expired",
    )
    decay_function: DecayFunctionType = DecayFunctionType.EXPONENTIAL
    enabled: bool = True

    def get_half_life(self, category: SignalCategory) -> float:
        """Return half-life for a category, falling back to 30 days."""
        return self.half_life_days.get(category.value, 30.0)

    def get_lambda(self, category: SignalCategory) -> float:
        """Return the decay constant λ = ln(2) / t½."""
        hl = self.get_half_life(category)
        if hl <= 0:
            return 0.0
        return math.log(2) / hl


# ─── Signal Activation Record ────────────────────────────────────────────────

class SignalActivation(BaseModel):
    """Tracks when a signal first fired for a specific ticker."""
    signal_id: str = Field(..., description="e.g. 'momentum.golden_cross'")
    ticker: str
    activated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    initial_strength: SignalStrength = SignalStrength.WEAK
    initial_confidence: float = Field(0.0, ge=0.0, le=1.0)
    category: SignalCategory
    half_life_days: float
    is_expired: bool = False


# ─── Decay-Adjusted Signal ───────────────────────────────────────────────────

class DecayAdjustedSignal(BaseModel):
    """An EvaluatedSignal enriched with temporal decay information."""
    # ── Original signal fields ──
    signal_id: str
    signal_name: str
    category: SignalCategory
    fired: bool = False
    value: float | None = None
    threshold: float = 0.0
    original_strength: SignalStrength = SignalStrength.WEAK
    original_confidence: float = Field(0.0, ge=0.0, le=1.0)
    description: str = ""

    # ── Decay fields ──
    signal_age_days: float = Field(
        0.0, ge=0.0, description="Days since the signal first activated",
    )
    half_life_days: float = Field(
        30.0, gt=0.0, description="Assigned half-life for this signal's category",
    )
    decay_factor: float = Field(
        1.0, ge=0.0, le=1.0,
        description="e^(-λt), 1.0 = fresh, 0.0 = fully decayed",
    )
    adjusted_confidence: float = Field(
        0.0, ge=0.0, le=1.0,
        description="original_confidence × decay_factor",
    )
    freshness: FreshnessLevel = FreshnessLevel.FRESH
    is_expired: bool = False

    @staticmethod
    def from_evaluated(
        sig: EvaluatedSignal,
        age_days: float,
        half_life: float,
        decay_factor: float,
        expiration_threshold: float = DEFAULT_EXPIRATION_THRESHOLD,
    ) -> DecayAdjustedSignal:
        """Factory: wrap an EvaluatedSignal with decay data."""
        adj_conf = sig.confidence * decay_factor if sig.fired else 0.0
        expired = decay_factor < expiration_threshold and sig.fired

        # Classify freshness
        if decay_factor >= 0.80:
            freshness = FreshnessLevel.FRESH
        elif decay_factor >= 0.50:
            freshness = FreshnessLevel.AGING
        elif decay_factor >= 0.20:
            freshness = FreshnessLevel.STALE
        else:
            freshness = FreshnessLevel.EXPIRED

        return DecayAdjustedSignal(
            signal_id=sig.signal_id,
            signal_name=sig.signal_name,
            category=sig.category,
            fired=sig.fired and not expired,
            value=sig.value,
            threshold=sig.threshold,
            original_strength=sig.strength,
            original_confidence=sig.confidence,
            description=sig.description,
            signal_age_days=round(age_days, 2),
            half_life_days=half_life,
            decay_factor=round(decay_factor, 4),
            adjusted_confidence=round(adj_conf, 4),
            freshness=freshness,
            is_expired=expired,
        )


# ─── Category Decay Summary ──────────────────────────────────────────────────

class CategoryDecaySummary(BaseModel):
    """Per-category aggregation with decay awareness."""
    category: SignalCategory
    active_signals: int = 0       # fired AND not expired
    expired_signals: int = 0      # fired but past expiration
    total_signals: int = 0
    average_decay_factor: float = Field(1.0, ge=0.0, le=1.0)
    freshness: FreshnessLevel = FreshnessLevel.FRESH


# ─── Decay-Adjusted Profile ──────────────────────────────────────────────────

class DecayAdjustedProfile(BaseModel):
    """
    A SignalProfile with temporal decay applied to all signals.

    This replaces SignalProfile as the input to the Composite Alpha Engine
    when decay is enabled.
    """
    ticker: str
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    total_signals: int = 0
    active_signals: int = 0       # fired AND not expired
    expired_signals: int = 0      # fired but past expiration
    signals: list[DecayAdjustedSignal] = Field(default_factory=list)
    category_summary: dict[str, CategoryDecaySummary] = Field(default_factory=dict)
    average_freshness: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Mean decay_factor across all fired signals (Freshness Index)",
    )
    overall_freshness: FreshnessLevel = FreshnessLevel.FRESH
    decay_config: DecayConfig = Field(default_factory=DecayConfig)
