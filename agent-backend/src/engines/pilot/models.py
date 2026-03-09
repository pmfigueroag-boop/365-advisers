"""
src/engines/pilot/models.py
─────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the 365 Advisers Pilot Deployment system.

Covers: pilot status, portfolio configs, daily snapshots, alerts,
signal/strategy/portfolio metrics, health status, reports, and dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from uuid import uuid4


# ─── Enumerations ───────────────────────────────────────────────────────────


class PilotPhase(str, Enum):
    """Lifecycle phases of the pilot."""
    SETUP = "setup"
    OBSERVATION = "observation"        # Weeks 2-4: monitor signals, no positions
    PAPER_TRADING = "paper_trading"    # Weeks 5-8: active paper trading
    EVALUATION = "evaluation"          # Weeks 9-12: full metric analysis
    COMPLETED = "completed"


class PilotAlertType(str, Enum):
    """Alert types specific to the pilot."""
    SIGNAL_DEGRADATION = "signal_degradation"
    STRATEGY_DRAWDOWN = "strategy_drawdown"
    STRATEGY_DRAWDOWN_CRITICAL = "strategy_drawdown_critical"
    PORTFOLIO_VOLATILITY_SPIKE = "portfolio_volatility_spike"
    PORTFOLIO_VOLATILITY_CRITICAL = "portfolio_volatility_critical"
    DATA_STALENESS = "data_staleness"
    CASE_SCORE_COLLAPSE = "case_score_collapse"
    CORRELATION_SPIKE = "correlation_spike"
    REGIME_CHANGE = "regime_change"


class PilotAlertSeverity(str, Enum):
    """Severity levels for pilot alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PortfolioType(str, Enum):
    """Types of pilot portfolios."""
    RESEARCH = "research"
    STRATEGY = "strategy"
    BENCHMARK = "benchmark"


class MetricLevel(str, Enum):
    """Metric aggregation levels."""
    SIGNAL = "signal"
    IDEA = "idea"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"
    SYSTEM = "system"


# ─── Portfolio Configuration ────────────────────────────────────────────────


class EntryExitCriteria(BaseModel):
    """Entry and exit rules for a pilot portfolio."""
    # Entry
    min_case_score: float = 65.0
    min_uos: float = 7.0
    min_active_signals: int = 3
    # Exit
    exit_case_score: float = 40.0
    trailing_stop_pct: float = 0.12
    time_stop_days: int = 30


class PilotPortfolioConfig(BaseModel):
    """Configuration for a single pilot portfolio."""
    portfolio_type: PortfolioType
    name: str
    sizing_method: str = "vol_parity"     # vol_parity | equal_weight | risk_budget
    max_positions: int = 20
    max_single_position_pct: float = 0.10
    max_sector_exposure_pct: float = 0.25
    rebalance_frequency: str = "weekly"   # daily | weekly | monthly
    initial_capital: float = 1_000_000.0

    # Entry/exit (not applicable for benchmark)
    entry_exit: EntryExitCriteria | None = None

    # Strategy blend (only for strategy portfolio)
    strategy_ids: list[str] = Field(default_factory=list)
    blend_method: str = "risk_parity"     # equal | risk_parity | momentum

    # Benchmark (only for benchmark portfolio)
    benchmark_weights: dict[str, float] = Field(default_factory=dict)

    # Regime rules
    regime_bear_action: str = "reduce_50"  # reduce_50 | no_new_entries | exit_all


# ─── Pilot Status ───────────────────────────────────────────────────────────


class PilotStatus(BaseModel):
    """Overall state of the pilot deployment."""
    pilot_id: str
    phase: PilotPhase = PilotPhase.SETUP
    current_week: int = 0
    total_weeks: int = 12
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_active: bool = True

    # Portfolio IDs (from Shadow Portfolio system)
    research_portfolio_id: str = ""
    strategy_portfolio_id: str = ""
    benchmark_portfolio_id: str = ""

    # Summary
    total_trading_days: int = 0
    total_alerts_generated: int = 0
    total_signals_evaluated: int = 0

    last_daily_run: datetime | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ─── Position Tracking ─────────────────────────────────────────────────────


class PilotPosition(BaseModel):
    """Individual position within a pilot portfolio."""
    ticker: str
    weight: float = 0.0               # 0.0 – 1.0 fraction of portfolio
    shares: float = 0.0               # Fractional shares allowed
    entry_price: float = 0.0
    current_price: float = 0.0
    position_pnl: float = 0.0         # Total unrealized P&L (USD)
    position_pnl_pct: float = 0.0     # Return %
    bucket: str = "satellite"          # "core" | "satellite" | "benchmark"
    entry_date: datetime | None = None
    signal_source: str = ""            # e.g. "CASE", "momentum_quality", "benchmark"


class PilotPortfolioState(BaseModel):
    """Aggregate state of a pilot portfolio at a point in time."""
    portfolio_id: str
    portfolio_type: PortfolioType
    positions: list[PilotPosition] = Field(default_factory=list)
    nav: float = 1_000_000.0
    cash: float = 1_000_000.0
    equity: float = 0.0               # Sum of position market values
    peak_nav: float = 1_000_000.0     # For drawdown tracking
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    drawdown: float = 0.0             # Current drawdown from peak
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )




class PilotDailySnapshot(BaseModel):
    """Point-in-time capture of a pilot portfolio's state."""
    pilot_id: str
    portfolio_id: str
    portfolio_type: PortfolioType
    snapshot_date: datetime

    # NAV
    nav: float = 1_000_000.0
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    drawdown: float = 0.0

    # Positions
    positions_count: int = 0
    active_ideas_count: int = 0

    # Signals
    signals_evaluated: int = 0
    signals_active: int = 0

    # Metrics snapshot
    metrics_json: dict[str, Any] = Field(default_factory=dict)


# ─── Alerts ─────────────────────────────────────────────────────────────────


class PilotAlert(BaseModel):
    """A pilot-specific alert."""
    id: str = Field(default_factory=lambda: uuid4().hex[:16])
    pilot_id: str
    alert_type: PilotAlertType
    severity: PilotAlertSeverity
    portfolio_id: str = ""
    title: str
    message: str = ""
    metric_name: str = ""
    current_value: float = 0.0
    threshold_value: float = 0.0
    auto_action: str = ""              # e.g. "pause_strategy", "reduce_exposure"
    resolved: bool = False
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ─── Metrics ────────────────────────────────────────────────────────────────


class PilotSignalMetrics(BaseModel):
    """Rolling signal-level metrics."""
    category: str = ""                 # signal category or "aggregate"
    hit_rate_5d: float = 0.0
    hit_rate_20d: float = 0.0
    avg_forward_return_5d: float = 0.0
    avg_forward_return_20d: float = 0.0
    information_coefficient: float = 0.0
    ic_ir: float = 0.0
    signal_turnover: float = 0.0
    signal_breadth: float = 0.0
    total_firings: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class PilotIdeaMetrics(BaseModel):
    """Idea quality metrics."""
    idea_type: str = ""                # detector type or "aggregate"
    hit_rate: float = 0.0
    avg_alpha: float = 0.0
    avg_decay_days: float = 0.0
    detector_precision: float = 0.0
    ideas_generated: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class PilotStrategyMetrics(BaseModel):
    """Per-strategy performance metrics."""
    strategy_id: str = ""
    strategy_name: str = ""
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win_loss_ratio: float = 0.0
    quality_score: float = 0.0        # 0-100 from SRL Scorecard
    regime_stability: str = ""         # "stable" | "unstable"
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class PilotPortfolioMetrics(BaseModel):
    """Portfolio-level performance metrics."""
    portfolio_id: str = ""
    portfolio_type: PortfolioType = PortfolioType.RESEARCH
    total_return: float = 0.0
    alpha_vs_benchmark: float = 0.0
    information_ratio: float = 0.0
    annualized_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    weekly_turnover: float = 0.0
    max_sector_concentration: float = 0.0
    brinson_allocation: float = 0.0
    brinson_selection: float = 0.0
    brinson_interaction: float = 0.0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ─── Health ─────────────────────────────────────────────────────────────────


class PilotHealthStatus(BaseModel):
    """System health indicators for the pilot."""
    pipeline_status: str = "idle"        # idle | running | complete | failed
    data_fresh: bool = True
    data_last_updated: datetime | None = None
    uptime_pct: float = 100.0
    active_strategies_count: int = 0
    target_strategies_count: int = 3
    queue_depth: int = 0
    critical_alerts_count: int = 0
    warning_alerts_count: int = 0
    last_run_duration_seconds: float = 0.0
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ─── Leaderboards ──────────────────────────────────────────────────────────


class SignalLeaderboardEntry(BaseModel):
    """A single entry in the signal leaderboard."""
    rank: int = 0
    signal_id: str = ""
    signal_name: str = ""
    category: str = ""
    hit_rate: float = 0.0
    avg_return: float = 0.0
    ic: float = 0.0
    total_firings: int = 0


class StrategyLeaderboardEntry(BaseModel):
    """A single entry in the strategy leaderboard."""
    rank: int = 0
    strategy_id: str = ""
    strategy_name: str = ""
    category: str = ""
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    quality_score: float = 0.0
    alpha: float = 0.0


# ─── Reports ────────────────────────────────────────────────────────────────


class PilotWeeklyReport(BaseModel):
    """Structured weekly report."""
    pilot_id: str
    week_number: int
    report_date: datetime

    # Portfolio performance
    portfolio_summaries: list[dict[str, Any]] = Field(default_factory=list)

    # Leaderboards
    signal_leaderboard: list[SignalLeaderboardEntry] = Field(default_factory=list)
    strategy_leaderboard: list[StrategyLeaderboardEntry] = Field(default_factory=list)

    # Observations
    observations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    alerts_this_week: int = 0

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ─── Success Criteria ──────────────────────────────────────────────────────


class SuccessCriterionResult(BaseModel):
    """Result of evaluating a single success criterion."""
    criterion_name: str
    description: str
    target_value: float
    actual_value: float
    passed: bool
    weight: float = 1.0


class PilotSuccessAssessment(BaseModel):
    """Go/No-Go assessment of the pilot."""
    pilot_id: str
    criteria_results: list[SuccessCriterionResult] = Field(default_factory=list)
    criteria_passed: int = 0
    criteria_total: int = 6
    recommendation: str = ""           # "GO" | "EXTEND" | "NO_GO"
    qualitative_notes: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ─── Dashboard ──────────────────────────────────────────────────────────────


class PilotDashboardData(BaseModel):
    """Aggregated data payload for the pilot dashboard."""
    pilot_status: PilotStatus

    # Equity curves (date → NAV for each portfolio)
    equity_curves: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)

    # Current positions per portfolio
    positions: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)

    # Active ideas
    active_ideas: list[dict[str, Any]] = Field(default_factory=list)

    # Performance comparison
    portfolio_metrics: list[PilotPortfolioMetrics] = Field(default_factory=list)

    # Health
    health: PilotHealthStatus = Field(default_factory=PilotHealthStatus)

    # Recent alerts
    recent_alerts: list[PilotAlert] = Field(default_factory=list)

    # Leaderboards
    signal_leaderboard: list[SignalLeaderboardEntry] = Field(default_factory=list)
    strategy_leaderboard: list[StrategyLeaderboardEntry] = Field(default_factory=list)

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
