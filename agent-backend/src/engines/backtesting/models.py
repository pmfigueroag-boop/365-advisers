"""
src/engines/backtesting/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Alpha Signal Backtesting Engine.

Defines configuration, signal events, performance records, category reports,
calibration suggestions, and the top-level backtest report.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from src.engines.alpha_signals.models import (
    SignalCategory,
    SignalStrength,
)


# ─── Backtest Run Status ─────────────────────────────────────────────────────

class BacktestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── Backtest Configuration ──────────────────────────────────────────────────

class BacktestConfig(BaseModel):
    """Configuration for a backtest run."""
    universe: list[str] = Field(
        ..., min_length=1, description="Ticker symbols to backtest",
    )
    start_date: date = Field(
        ..., description="Start of historical lookback window",
    )
    end_date: date = Field(
        default_factory=lambda: date.today(),
        description="End of lookback window",
    )
    forward_windows: list[int] = Field(
        default=[1, 5, 10, 20, 60],
        description="T+N days for forward return measurement",
    )
    min_observations: int = Field(
        30, ge=5,
        description="Minimum signal firings required for valid statistics",
    )
    signal_ids: list[str] | None = Field(
        None,
        description="Specific signal IDs to test (None = all enabled)",
    )
    benchmark_ticker: str = Field(
        "SPY", description="Benchmark for excess return calculation",
    )
    cooldown_factor: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Cooldown = forward_window × cooldown_factor",
    )
    cost_model_enabled: bool = Field(
        False, description="Apply transaction cost adjustments",
    )
    cost_config: dict | None = Field(
        None, description="CostModelConfig params (if None, defaults are used)",
    )


# ─── Signal Event (ephemeral, per-run) ───────────────────────────────────────

class SignalEvent(BaseModel):
    """A single historical signal firing event."""
    signal_id: str
    ticker: str
    fired_date: date
    strength: SignalStrength
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    value: float
    price_at_fire: float
    forward_returns: dict[int, float] = Field(
        default_factory=dict,
        description="{window_days: return_pct}",
    )
    benchmark_returns: dict[int, float] = Field(
        default_factory=dict,
        description="Benchmark returns for the same windows",
    )
    excess_returns: dict[int, float] = Field(
        default_factory=dict,
        description="forward - benchmark returns",
    )
    adjusted_returns: dict[int, float] = Field(
        default_factory=dict,
        description="Forward returns net of transaction costs",
    )
    total_cost: float = Field(
        0.0, description="Total round-trip cost as fraction of notional",
    )


# ─── Per-Signal Performance Record ───────────────────────────────────────────

class SignalPerformanceRecord(BaseModel):
    """Aggregated backtest results for a single signal definition."""
    signal_id: str
    signal_name: str
    category: SignalCategory

    # ── Core Metrics ──
    total_firings: int = 0
    hit_rate: dict[int, float] = Field(
        default_factory=dict,
        description="{window: hit_rate_pct}",
    )
    avg_return: dict[int, float] = Field(
        default_factory=dict,
        description="{window: avg_return_pct}",
    )
    avg_excess_return: dict[int, float] = Field(
        default_factory=dict,
        description="{window: avg_excess_return_pct}",
    )
    median_return: dict[int, float] = Field(
        default_factory=dict,
        description="{window: median_return_pct}",
    )

    # ── Risk-Adjusted Metrics ──
    sharpe_ratio: dict[int, float] = Field(
        default_factory=dict,
        description="Annualised Sharpe per window",
    )
    sortino_ratio: dict[int, float] = Field(
        default_factory=dict,
        description="Annualised Sortino per window",
    )
    max_drawdown: float = 0.0

    # ── Decay / Timing Metrics ──
    empirical_half_life: float | None = Field(
        None, description="Days until avg excess return decays to 50%",
    )
    optimal_hold_period: int | None = Field(
        None, description="Forward window with best Sharpe",
    )
    alpha_decay_curve: list[float] = Field(
        default_factory=list,
        description="Avg daily excess return for days 1..60",
    )

    # ── Statistical Confidence ──
    t_statistic: dict[int, float] = Field(
        default_factory=dict, description="Per-window t-statistics",
    )
    p_value: dict[int, float] = Field(
        default_factory=dict, description="Per-window p-values",
    )
    confidence_level: str = "LOW"
    sample_size: int = 0

    # ── Metadata ──
    backtest_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    universe_size: int = 0
    date_range: str = ""


# ─── Category Performance Report ────────────────────────────────────────────

class CategoryPerformanceReport(BaseModel):
    """Aggregated performance across all signals in a category."""
    category: SignalCategory
    signal_count: int = 0
    avg_hit_rate: float = 0.0
    avg_sharpe: float = 0.0
    best_signal: str = ""
    worst_signal: str = ""
    category_alpha: float = 0.0
    empirical_half_life: float | None = None
    correlation_matrix: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Inter-signal return correlations",
    )


# ─── Calibration Suggestion ─────────────────────────────────────────────────

class CalibrationSuggestion(BaseModel):
    """Suggested parameter adjustment based on backtest evidence."""
    signal_id: str
    parameter: str = Field(
        ..., description="'threshold' | 'weight' | 'half_life'",
    )
    current_value: float
    suggested_value: float
    evidence: str
    impact_estimate: str = ""


# ─── Full Backtest Report ────────────────────────────────────────────────────

class BacktestReport(BaseModel):
    """Complete output of a backtesting run."""
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    config: BacktestConfig
    signal_results: list[SignalPerformanceRecord] = Field(default_factory=list)
    category_summaries: list[CategoryPerformanceReport] = Field(
        default_factory=list,
    )
    top_signals: list[str] = Field(
        default_factory=list,
        description="Top 10 signal IDs by Sharpe ratio",
    )
    underperforming_signals: list[str] = Field(
        default_factory=list,
        description="Signals with negative average alpha",
    )
    calibration_suggestions: list[CalibrationSuggestion] = Field(
        default_factory=list,
    )
    completed_at: datetime | None = None
    execution_time_seconds: float = 0.0
    status: BacktestStatus = BacktestStatus.PENDING
    error_message: str | None = None


# ─── Backtest Run Summary (for listing) ─────────────────────────────────────

class BacktestRunSummary(BaseModel):
    """Compact summary of a backtest run for list views."""
    run_id: str
    universe_size: int
    signal_count: int
    status: BacktestStatus
    date_range: str
    created_at: datetime
    execution_time_seconds: float = 0.0


# ─── Signal Performance Database Models ─────────────────────────────────────

class SignalPerformanceEvent(BaseModel):
    """Persisted individual signal firing with forward returns."""
    signal_id: str
    signal_name: str = ""
    ticker: str
    fired_date: date
    strength: str               # strong|moderate|weak
    confidence: float = 0.0
    value: float
    price_at_fire: float
    forward_returns: dict[int, float] = Field(default_factory=dict)
    benchmark_returns: dict[int, float] = Field(default_factory=dict)
    excess_returns: dict[int, float] = Field(default_factory=dict)
    run_id: str = ""


class CalibrationRecord(BaseModel):
    """Audit record for a signal parameter recalibration."""
    signal_id: str
    parameter: str              # threshold|weight|half_life
    old_value: float
    new_value: float
    evidence: str
    run_id: str = ""
    applied_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    applied_by: str = "auto"


# ─── Quality Tier ────────────────────────────────────────────────────────────

TIER_MULTIPLIERS: dict[str, float] = {
    "A": 1.3,
    "B": 1.0,
    "C": 0.7,
    "D": 0.4,
}


class SignalScorecard(BaseModel):
    """Live scorecard for a signal, derived from stored performance events."""
    signal_id: str
    signal_name: str = ""
    category: str = ""
    total_events: int = 0
    hit_rate_20d: float = 0.0
    avg_return_20d: float = 0.0
    sharpe_20d: float = 0.0
    confidence_level: str = "LOW"   # HIGH|MEDIUM|LOW
    empirical_half_life: float | None = None
    last_calibrated: datetime | None = None
    quality_tier: str = "D"         # A|B|C|D


# ─── Combination Backtest Result ─────────────────────────────────────────────

class CombinationBacktestResult(BaseModel):
    """Result of testing a signal combination (AND logic)."""
    combination_id: str = Field(
        ..., description="Canonical key, e.g. 'sig_a+sig_b+sig_c'",
    )
    signal_ids: list[str]
    joint_firings: int = 0
    individual_firings: dict[str, int] = Field(
        default_factory=dict,
        description="{signal_id: individual_firing_count}",
    )
    hit_rate: dict[int, float] = Field(
        default_factory=dict,
        description="{window: hit_rate} for joint firings",
    )
    avg_return: dict[int, float] = Field(default_factory=dict)
    avg_excess_return: dict[int, float] = Field(default_factory=dict)
    sharpe: dict[int, float] = Field(default_factory=dict)
    incremental_alpha: float = Field(
        0.0,
        description="Excess alpha vs. best individual signal (T+20)",
    )
    synergy_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Diversification benefit: 1.0 = max synergy",
    )
    backtest_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ─── Regime Performance Report ───────────────────────────────────────────────

class RegimePerformanceReport(BaseModel):
    """Per-regime breakdown of signal performance."""
    signal_id: str
    signal_name: str = ""
    regime_results: dict[str, SignalPerformanceRecord] = Field(
        default_factory=dict,
        description="{regime_label: performance_record}",
    )
    best_regime: str = ""
    worst_regime: str = ""
    regime_stability: float = Field(
        0.0,
        description="StdDev of Sharpe across regimes (lower = more stable)",
    )
    backtest_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

