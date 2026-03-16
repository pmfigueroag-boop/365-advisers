"""
src/research/alpha_tests/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Alpha Discrimination Test.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class BucketMetrics(BaseModel):
    """Per-quintile/tercile performance statistics."""

    bucket_label: str                          # Q1, Q2 … Q5
    score_min: float = 0.0
    score_max: float = 0.0
    count: int = 0
    mean_return_5d: float = 0.0
    mean_return_20d: float = 0.0
    median_return_5d: float = 0.0
    median_return_20d: float = 0.0
    std_return_5d: float = 0.0
    std_return_20d: float = 0.0
    hit_rate_5d: float = 0.0                   # % with return > 0
    hit_rate_20d: float = 0.0


class AlphaDecayPoint(BaseModel):
    """Single point on the alpha decay curve."""

    horizon_label: str                         # "1d", "5d", "20d", "60d"
    horizon_days: int
    alpha_spread: float | None = None          # Q5 − Q1 at this horizon


class SignificanceResult(BaseModel):
    """Statistical significance metrics."""

    welch_t_statistic: float | None = None
    welch_p_value: float | None = None
    spearman_correlation: float = 0.0
    spearman_p_value: float | None = None
    bootstrap_ci_lower: float | None = None    # 95% CI on alpha_spread_20d
    bootstrap_ci_upper: float | None = None
    kendall_tau: float | None = None           # Monotonicity measure


class AlphaSpreadResult(BaseModel):
    """Complete output of a single-score quintile spread test."""

    score_column: str
    observations: int = 0
    observations_after_dedup: int = 0
    n_buckets: int = 5
    buckets: list[BucketMetrics] = Field(default_factory=list)

    # Core spreads
    alpha_spread_5d: float = 0.0
    alpha_spread_20d: float = 0.0

    # Significance
    significance: SignificanceResult = Field(default_factory=SignificanceResult)

    # Alpha decay
    alpha_decay_curve: list[AlphaDecayPoint] = Field(default_factory=list)

    # Acceptance
    signal: str = "No data"
    acceptance_details: dict = Field(default_factory=dict)

    # Warnings
    warnings: list[str] = Field(default_factory=list)

    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class ScoreTestComparison(BaseModel):
    """Multi-score comparison: runs the test for each score dimension."""

    results: dict[str, AlphaSpreadResult] = Field(default_factory=dict)
    best_score: str = ""
    best_alpha_spread_20d: float = 0.0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
