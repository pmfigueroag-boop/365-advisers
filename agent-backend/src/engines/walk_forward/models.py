"""
src/engines/walk_forward/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Walk-Forward Validation Engine.

Defines configuration, per-fold results, aggregated signal summaries,
stability classifications, and the complete run report.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from src.engines.alpha_signals.models import SignalCategory


# ─── Enumerations ────────────────────────────────────────────────────────────

class WalkForwardMode(str, Enum):
    """Window sliding strategy."""
    ROLLING = "rolling"      # Fixed-size window slides forward
    ANCHORED = "anchored"    # Start fixed, window grows each fold


class StabilityClassification(str, Enum):
    """Cross-fold stability rating for a signal."""
    ROBUST = "robust"        # ≥ 0.75
    MODERATE = "moderate"    # 0.50–0.74
    WEAK = "weak"            # 0.25–0.49
    OVERFIT = "overfit"      # < 0.25


# ─── Configuration ───────────────────────────────────────────────────────────

class WalkForwardConfig(BaseModel):
    """Configuration for a walk-forward validation run."""

    universe: list[str] = Field(
        ..., min_length=1, description="Ticker symbols to validate",
    )
    start_date: date = Field(
        ..., description="Earliest date for the first train window",
    )
    end_date: date = Field(
        default_factory=date.today, description="Latest date for the last test window",
    )
    train_days: int = Field(
        756, ge=126,
        description="In-sample window length in trading days (≈3 years)",
    )
    test_days: int = Field(
        126, ge=21,
        description="Out-of-sample window length in trading days (≈6 months)",
    )
    step_days: int | None = Field(
        None,
        description="Step size in trading days (default = test_days)",
    )
    mode: WalkForwardMode = Field(
        WalkForwardMode.ROLLING,
        description="'rolling' (fixed window) or 'anchored' (growing window)",
    )
    min_train_events: int = Field(
        30, ge=5,
        description="Minimum signal firings required in IS to qualify",
    )
    signal_ids: list[str] | None = Field(
        None, description="Specific signal IDs (None = all enabled)",
    )
    benchmark_ticker: str = Field(
        "SPY", description="Benchmark for excess return calculation",
    )
    forward_windows: list[int] = Field(
        default_factory=lambda: [5, 10, 20],
        description="Forward-return windows in trading days",
    )
    is_hit_rate_threshold: float = Field(
        0.50, ge=0.0, le=1.0,
        description="Minimum IS hit rate to qualify for OOS",
    )
    is_sharpe_threshold: float = Field(
        0.0,
        description="Minimum IS Sharpe to qualify for OOS",
    )
    cooldown_factor: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Cooldown = forward_window × cooldown_factor",
    )

    @property
    def effective_step_days(self) -> int:
        return self.step_days if self.step_days is not None else self.test_days


# ─── Fold Definition ─────────────────────────────────────────────────────────

class WalkForwardFold(BaseModel):
    """A single train/test temporal split."""
    fold_index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date


# ─── Per-Fold Signal Result ──────────────────────────────────────────────────

class WFSignalFoldResult(BaseModel):
    """In-sample and out-of-sample metrics for one signal in one fold."""
    signal_id: str
    signal_name: str = ""
    fold_index: int
    # In-Sample metrics
    is_hit_rate: float = 0.0
    is_sharpe: float = 0.0
    is_alpha: float = 0.0
    is_firings: int = 0
    qualified: bool = False
    # Out-of-Sample metrics (populated only if qualified)
    oos_hit_rate: float | None = None
    oos_sharpe: float | None = None
    oos_alpha: float | None = None
    oos_firings: int = 0


# ─── Aggregated Signal Summary ───────────────────────────────────────────────

class WFSignalSummary(BaseModel):
    """Cross-fold stability summary for a single signal."""
    signal_id: str
    signal_name: str = ""
    category: SignalCategory
    total_folds: int = 0
    qualified_folds: int = 0
    # Aggregated OOS metrics (mean across qualified folds)
    avg_oos_hit_rate: float = 0.0
    avg_oos_sharpe: float = 0.0
    avg_oos_alpha: float = 0.0
    total_oos_firings: int = 0
    # Stability components
    stability_score: float = 0.0
    stability_class: StabilityClassification = StabilityClassification.OVERFIT
    consistency_ratio: float = 0.0
    sharpe_stability: float = 0.0
    alpha_persistence: float = 0.0
    qualification_rate: float = 0.0
    # Per-fold detail
    fold_results: list[WFSignalFoldResult] = Field(default_factory=list)


# ─── Complete Run Report ─────────────────────────────────────────────────────

class WalkForwardRun(BaseModel):
    """Complete output of a walk-forward validation run."""
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    config: WalkForwardConfig
    total_folds: int = 0
    folds: list[WalkForwardFold] = Field(default_factory=list)
    signal_summaries: list[WFSignalSummary] = Field(default_factory=list)
    robust_signals: list[str] = Field(
        default_factory=list,
        description="Signal IDs with stability ≥ ROBUST",
    )
    overfit_signals: list[str] = Field(
        default_factory=list,
        description="Signal IDs classified as OVERFIT",
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    completed_at: datetime | None = None
    execution_time_seconds: float = 0.0
    status: str = "pending"
    error_message: str | None = None
