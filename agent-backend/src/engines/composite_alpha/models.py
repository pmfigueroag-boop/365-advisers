"""
src/engines/composite_alpha/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Composite Alpha Score Engine (CASE).

Defines the output structures, weight configuration, and the semantic
signal environment classification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from src.engines.alpha_signals.models import SignalCategory, SignalProfile
from src.engines.alpha_decay.models import FreshnessLevel


# ─── Signal Environment Classification ───────────────────────────────────────

class SignalEnvironment(str, Enum):
    """Semantic label for the composite alpha score."""
    VERY_STRONG = "Very Strong Opportunity"
    STRONG = "Strong Opportunity"
    NEUTRAL = "Neutral"
    WEAK = "Weak"
    NEGATIVE = "Negative Signal Environment"


# ─── Category Subscore ────────────────────────────────────────────────────────

class CategorySubscore(BaseModel):
    """0–100 subscore for a single signal category."""
    category: SignalCategory
    score: float = Field(0.0, ge=0.0, le=100.0)
    fired: int = 0
    total: int = 0
    coverage: float = Field(0.0, ge=0.0, le=1.0)
    conflict_detected: bool = False
    conflict_penalty: float = Field(1.0, ge=0.0, le=1.0)
    top_signals: list[str] = Field(
        default_factory=list,
        description="Names of the top 3 strongest fired signals in this category",
    )


# ─── Weight Configuration ────────────────────────────────────────────────────

class CASEWeightConfig(BaseModel):
    """
    Configurable weight profile for category aggregation.

    Weights must sum to 1.0.  Default profile reflects academic factor
    research consensus:
      - Value (25%):      Most-documented factor (Fama-French 1993, 2015)
      - Quality (22%):    High persistence (Novy-Marx 2013, Asness et al 2019)
      - Momentum (20%):   Strong returns, crash risk (Jegadeesh & Titman 1993)
      - Growth (15%):     Noisy without quality adjustment
      - Flow (8%):        Signal strength varies
      - Volatility (5%):  Informative but not directionally predictive
      - Event (3%):       Low signal/noise ratio
      - Macro (2%):       Background context, not stock-specific
    """
    value: float = 0.25
    quality: float = 0.22
    momentum: float = 0.20
    growth: float = 0.15
    flow: float = 0.08
    volatility: float = 0.05
    event: float = 0.03
    macro: float = 0.02

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> CASEWeightConfig:
        total = (
            self.value + self.quality + self.momentum + self.growth
            + self.flow + self.volatility + self.event + self.macro
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Category weights must sum to 1.0, got {total:.4f}"
            )
        return self

    def as_dict(self) -> dict[str, float]:
        """Return weights keyed by SignalCategory value strings."""
        return {
            SignalCategory.VALUE.value: self.value,
            SignalCategory.QUALITY.value: self.quality,
            SignalCategory.MOMENTUM.value: self.momentum,
            SignalCategory.GROWTH.value: self.growth,
            SignalCategory.FLOW.value: self.flow,
            SignalCategory.VOLATILITY.value: self.volatility,
            SignalCategory.EVENT.value: self.event,
            SignalCategory.MACRO.value: self.macro,
        }


# ─── Composite Alpha Result ──────────────────────────────────────────────────

class CompositeAlphaResult(BaseModel):
    """Complete output of the Composite Alpha Score Engine for one asset."""
    ticker: str
    composite_alpha_score: float = Field(0.0, ge=0.0, le=100.0)
    signal_environment: SignalEnvironment = SignalEnvironment.NEUTRAL
    subscores: dict[str, CategorySubscore] = Field(default_factory=dict)
    active_categories: int = 0
    convergence_bonus: float = 0.0
    cross_category_conflicts: list[str] = Field(default_factory=list)
    weight_profile: dict[str, float] = Field(default_factory=dict)
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    signal_profile: SignalProfile | None = Field(
        None, description="Reference to the source SignalProfile",
    )
    # ── Decay-awareness fields ──
    decay_applied: bool = Field(False, description="Whether decay was active")
    average_freshness: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Mean decay factor across fired signals (1.0 = all fresh)",
    )
    expired_signal_count: int = Field(
        0, description="Number of signals excluded due to expiration",
    )
    freshness_level: FreshnessLevel = FreshnessLevel.FRESH
