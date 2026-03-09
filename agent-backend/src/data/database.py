"""
src/data/database.py
─────────────────────────────────────────────────────────────────────────────
Persistence layer using SQLAlchemy (sync engine).
Supports PostgreSQL (recommended) and SQLite (dev fallback).

Tables:
  fundamental_analyses  — full snapshots, 24h cache backing
  technical_analyses    — full snapshots, 15min cache backing
  score_history         — time-series of scores for charts
  (+ 13 more tables for engines, backtesting, signals, etc.)

The DB-backed cache classes (FundamentalDBCache, TechnicalDBCache) expose
the same .get()/.set()/.invalidate() interface as the in-memory caches,
making them drop-in replacements in main.py.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean, Column, Integer, Float, String, Text, DateTime,
    Index, create_engine, text, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, relationship


# ─── Database setup ───────────────────────────────────────────────────────────

def _build_engine():
    """Create the SQLAlchemy engine from DATABASE_URL config.

    For PostgreSQL: enables connection pooling for multi-user concurrency.
    For SQLite: uses NullPool (no pooling, as SQLite is single-writer).
    """
    from src.config import get_settings
    url = get_settings().DATABASE_URL

    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        # SQLite fallback for local dev
        return create_engine(
            url, echo=False,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL with connection pool
        return create_engine(
            url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )


ENGINE = _build_engine()
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# ─── Models ───────────────────────────────────────────────────────────────────

class FundamentalAnalysis(Base):
    __tablename__ = "fundamental_analyses"
    __table_args__ = (
        Index("idx_fund_ticker_date", "ticker", "analyzed_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    analyzed_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    signal          = Column(String(10))            # BUY | SELL | HOLD
    score           = Column(Float)                 # 0–10
    confidence      = Column(Float)
    risk_adj_score  = Column(Float)
    allocation      = Column(String(30))
    committee_json  = Column(Text)                  # CommitteeOutput dict
    agent_memos_json= Column(Text)                  # list of AgentMemo
    ratios_json     = Column(Text)                  # fundamental ratios snapshot
    research_memo   = Column(Text)                  # 1-pager markdown
    expires_at      = Column(Float)                 # Unix timestamp


class TechnicalAnalysis(Base):
    __tablename__ = "technical_analyses"
    __table_args__ = (
        Index("idx_tech_ticker_date", "ticker", "interval", "analyzed_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    interval        = Column(String(8), default="1D")
    analyzed_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    signal          = Column(String(20))            # STRONG_BUY … STRONG_SELL
    technical_score = Column(Float)
    trend_status    = Column(String(20))
    momentum_status = Column(String(20))
    signal_strength = Column(String(10))
    summary_json    = Column(Text)                  # full TechnicalSummary
    indicators_json = Column(Text)                  # raw indicator snapshot
    expires_at      = Column(Float)


class ScoreHistory(Base):
    __tablename__ = "score_history"
    __table_args__ = (
        Index("idx_score_history", "ticker", "analysis_type", "recorded_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    analysis_type   = Column(String(15), nullable=False)  # fundamental | technical
    recorded_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    score           = Column(Float)
    signal          = Column(String(20))


class OpportunityScoreHistory(Base):
    __tablename__ = "opportunity_score_history"
    __table_args__ = (
        Index("idx_opp_score_history", "ticker", "recorded_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    recorded_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    opportunity_score = Column(Float)               # 0-10
    business_quality  = Column(Float)               # 0-10
    valuation         = Column(Float)               # 0-10
    financial_strength= Column(Float)               # 0-10
    market_behavior   = Column(Float)               # 0-10
    score_breakdown_json = Column(Text)             # Full 12-factor JSON payload


class Portfolio(Base):
    __tablename__ = "portfolios"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    name             = Column(String(100), nullable=False)
    strategy         = Column(String(100))
    risk_level       = Column(String(50))
    total_allocation = Column(Float)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship to positions
    positions        = relationship("PortfolioPosition", back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id     = Column(Integer, ForeignKey("portfolios.id"), nullable=False, index=True)
    ticker           = Column(String(16), nullable=False)
    target_weight    = Column(Float, nullable=False)
    role             = Column(String(20))           # CORE | SATELLITE
    sector           = Column(String(100))
    volatility_atr   = Column(Float)

    # Relationship back to Portfolio
    portfolio        = relationship("Portfolio", back_populates="positions")


class IdeaRecord(Base):
    """Persisted investment idea generated by the Idea Generation Engine."""
    __tablename__ = "ideas"
    __table_args__ = (
        Index("idx_ideas_status_priority", "status", "priority"),
        Index("idx_ideas_ticker", "ticker", "generated_at"),
    )

    id               = Column(Integer, primary_key=True, autoincrement=True)
    idea_uid         = Column(String(16), nullable=False, unique=True)
    ticker           = Column(String(16), nullable=False, index=True)
    name             = Column(String(200), default="")
    sector           = Column(String(100), default="")
    idea_type        = Column(String(20), nullable=False)   # value|quality|momentum|reversal|event
    confidence       = Column(String(10), nullable=False)   # high|medium|low
    signal_strength  = Column(Float, nullable=False)
    priority         = Column(Integer, nullable=False, default=0)
    signals_json     = Column(Text, nullable=False)         # JSON array of SignalDetail
    status           = Column(String(20), default="active") # active|analyzed|dismissed
    generated_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at       = Column(DateTime)
    analyzed_at      = Column(DateTime)                     # set when user runs full analysis
    metadata_json    = Column(Text, default="{}")


class SignalSnapshot(Base):
    """Persisted alpha signal evaluation snapshot for a single ticker."""
    __tablename__ = "signal_snapshots"
    __table_args__ = (
        Index("idx_signal_snapshots_ticker", "ticker", "evaluated_at"),
        Index("idx_signal_snapshots_category", "ticker", "category", "evaluated_at"),
    )

    id                = Column(Integer, primary_key=True, autoincrement=True)
    ticker            = Column(String(16), nullable=False, index=True)
    evaluated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    category          = Column(String(20), nullable=False)       # value|quality|momentum|...
    signals_json      = Column(Text, nullable=False)             # JSON array of EvaluatedSignal
    composite_strength= Column(Float, nullable=False, default=0.0)
    confidence        = Column(String(10), nullable=False)       # high|medium|low
    fired_count       = Column(Integer, default=0)
    total_count       = Column(Integer, default=0)
    scan_id           = Column(String(20))                       # Optional reference to IGE scan


class CompositeAlphaHistory(Base):
    """Persisted Composite Alpha Score for historical tracking."""
    __tablename__ = "composite_alpha_history"
    __table_args__ = (
        Index("idx_composite_alpha_ticker", "ticker", "evaluated_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    score           = Column(Float, nullable=False)
    environment     = Column(String(30), nullable=False)
    subscores_json  = Column(Text, nullable=False)           # JSON blob of category subscores
    active_categories = Column(Integer, default=0)
    conflicts_json  = Column(Text, default="[]")             # JSON array of conflict descriptions
    evaluated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class SignalActivationRecord(Base):
    """Persisted activation timestamps for the Alpha Decay engine."""
    __tablename__ = "signal_activations"
    __table_args__ = (
        Index("idx_signal_activations_ticker", "ticker", "is_expired"),
        Index("idx_signal_activations_signal", "signal_id", "ticker", "is_expired"),
    )

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    signal_id          = Column(String(64), nullable=False)
    ticker             = Column(String(16), nullable=False, index=True)
    activated_at       = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    deactivated_at     = Column(DateTime, nullable=True)
    initial_strength   = Column(String(10), default="weak")
    initial_confidence = Column(Float, default=0.0)
    category           = Column(String(20), nullable=False)
    half_life_days     = Column(Float, nullable=False, default=30.0)
    is_expired         = Column(Boolean, default=False)


# ─── Backtesting Tables ──────────────────────────────────────────────────────

class BacktestRun(Base):
    """Persisted metadata for a single backtesting run."""
    __tablename__ = "backtest_runs"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    run_id           = Column(String(36), nullable=False, unique=True, index=True)
    universe_json    = Column(Text, nullable=False)           # JSON list of tickers
    start_date       = Column(String(10), nullable=False)     # ISO date
    end_date         = Column(String(10), nullable=False)
    signal_count     = Column(Integer, default=0)
    status           = Column(String(20), default="pending")  # pending|running|completed|failed
    execution_time_s = Column(Float, default=0.0)
    config_json      = Column(Text, default="{}")             # Full BacktestConfig
    calibration_json = Column(Text, default="[]")             # CalibrationSuggestion list
    error_message    = Column(Text)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship to results
    results          = relationship("BacktestResult", back_populates="run", cascade="all, delete-orphan")


class BacktestResult(Base):
    """Persisted per-signal performance results from a backtest run."""
    __tablename__ = "backtest_results"
    __table_args__ = (
        Index("idx_backtest_results_run", "run_id", "signal_id"),
        Index("idx_backtest_results_signal", "signal_id", "created_at"),
    )

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    run_id                   = Column(String(36), ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    signal_id                = Column(String(50), nullable=False)
    signal_name              = Column(String(100))
    category                 = Column(String(20))
    total_firings            = Column(Integer, default=0)
    hit_rate_json            = Column(Text, default="{}")     # {window: rate}
    avg_return_json          = Column(Text, default="{}")
    avg_excess_return_json   = Column(Text, default="{}")
    median_return_json       = Column(Text, default="{}")
    sharpe_json              = Column(Text, default="{}")
    sortino_json             = Column(Text, default="{}")
    max_drawdown             = Column(Float, default=0.0)
    empirical_half_life      = Column(Float)
    optimal_hold_period      = Column(Integer)
    alpha_decay_curve_json   = Column(Text, default="[]")     # 60-element array
    t_statistic_json         = Column(Text, default="{}")
    p_value_json             = Column(Text, default="{}")
    confidence_level         = Column(String(10), default="LOW")
    sample_size              = Column(Integer, default=0)
    universe_size            = Column(Integer, default=0)
    date_range               = Column(String(50))
    created_at               = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship back to run
    run                      = relationship("BacktestRun", back_populates="results")


class SignalPerformanceEventRecord(Base):
    """Persisted individual signal firing with forward returns."""
    __tablename__ = "signal_performance_events"
    __table_args__ = (
        Index("idx_perf_events_signal_ticker", "signal_id", "ticker", "fired_date"),
        Index("idx_perf_events_ticker", "ticker", "fired_date"),
    )

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    signal_id             = Column(String(50), nullable=False, index=True)
    signal_name           = Column(String(100))
    ticker                = Column(String(16), nullable=False, index=True)
    fired_date            = Column(String(10), nullable=False)         # ISO date
    strength              = Column(String(10), nullable=False)         # strong|moderate|weak
    confidence            = Column(Float, default=0.0)                 # 0.0–1.0
    value                 = Column(Float)                              # Feature value at fire
    price_at_fire         = Column(Float)
    forward_returns_json  = Column(Text, default="{}")                 # {window: return}
    benchmark_returns_json= Column(Text, default="{}")
    excess_returns_json   = Column(Text, default="{}")
    run_id                = Column(String(36), ForeignKey("backtest_runs.run_id"), index=True)
    created_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SignalCalibrationHistoryRecord(Base):
    """Audit trail for signal parameter recalibrations."""
    __tablename__ = "signal_calibration_history"
    __table_args__ = (
        Index("idx_calibration_signal", "signal_id", "applied_at"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    signal_id     = Column(String(50), nullable=False, index=True)
    parameter     = Column(String(20), nullable=False)    # threshold|weight|half_life
    old_value     = Column(Float, nullable=False)
    new_value     = Column(Float, nullable=False)
    evidence      = Column(Text)
    run_id        = Column(String(36))                    # Backtest run that produced this
    applied_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    applied_by    = Column(String(20), default="auto")    # auto|manual



class OpportunityAlertRecord(Base):
    """Persistent store for opportunity monitoring alerts."""
    __tablename__ = "opportunity_alerts"
    __table_args__ = (
        Index("idx_opp_alerts_ticker", "ticker", "created_at"),
        Index("idx_opp_alerts_severity", "severity", "read", "created_at"),
    )

    id          = Column(String(64), primary_key=True)
    ticker      = Column(String(16), nullable=False, index=True)
    alert_type  = Column(String(30), nullable=False)
    severity    = Column(String(20), nullable=False)
    title       = Column(String(200))
    description = Column(Text)
    prev_value  = Column(Float)
    curr_value  = Column(Float)
    delta       = Column(Float)
    new_signals = Column(Text)          # JSON list
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    read        = Column(Boolean, default=False)


# ─── Quantitative Validation Framework Tables ────────────────────────────────

class RollingPerformanceRecord(Base):
    """Rolling performance snapshots for degradation monitoring."""
    __tablename__ = "rolling_performance"
    __table_args__ = (
        Index("idx_rolling_perf", "signal_id", "window_days", "as_of_date"),
    )

    id           = Column(Integer, primary_key=True, autoincrement=True)
    signal_id    = Column(String(50), nullable=False, index=True)
    window_days  = Column(Integer, nullable=False)          # 30, 90, 252
    as_of_date   = Column(String(10), nullable=False)       # ISO date
    hit_rate     = Column(Float)
    sharpe       = Column(Float)
    avg_return   = Column(Float)
    avg_excess   = Column(Float)
    sample_size  = Column(Integer)
    regime       = Column(String(20))                       # bull|bear|range|null
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OpportunityPerformanceRecord(Base):
    """Forward performance tracking for generated ideas."""
    __tablename__ = "opportunity_performance"
    __table_args__ = (
        Index("idx_opp_perf_ticker", "ticker", "generated_at"),
        Index("idx_opp_perf_type", "idea_type", "generated_at"),
    )

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    idea_uid             = Column(String(16), nullable=False, index=True)
    ticker               = Column(String(16), nullable=False, index=True)
    idea_type            = Column(String(20), nullable=False)
    confidence           = Column(String(10), nullable=False)
    signal_strength      = Column(Float, nullable=False)
    opportunity_score    = Column(Float)                     # UOS at generation time
    suggested_alloc      = Column(Float)                     # % allocation suggested
    price_at_gen         = Column(Float)                     # Price when idea was generated
    generated_at         = Column(DateTime, nullable=False)
    # Forward returns (filled asynchronously by tracker)
    return_1d            = Column(Float)
    return_5d            = Column(Float)
    return_20d           = Column(Float)
    return_60d           = Column(Float)
    benchmark_return_20d = Column(Float)
    excess_return_20d    = Column(Float)
    tracking_status      = Column(String(20), default="pending")  # pending|partial|complete
    last_updated         = Column(DateTime)


class DegradationAlertRecord(Base):
    """Persistent record of signal degradation detections."""
    __tablename__ = "degradation_alerts"
    __table_args__ = (
        Index("idx_degradation_signal", "signal_id", "detected_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    signal_id       = Column(String(50), nullable=False, index=True)
    signal_name     = Column(String(100))
    metric          = Column(String(30), nullable=False)
    peak_value      = Column(Float, nullable=False)
    current_value   = Column(Float, nullable=False)
    decline_pct     = Column(Float, nullable=False)
    recommendation  = Column(String(20), nullable=False)
    action_taken    = Column(String(20), default="none")    # none|weight_reduced|disabled
    detected_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at     = Column(DateTime)


# ─── Walk-Forward Validation Tables ──────────────────────────────────────────

class WalkForwardRunRecord(Base):
    """Metadata for a walk-forward validation run."""
    __tablename__ = "walk_forward_runs"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    run_id           = Column(String(36), nullable=False, unique=True, index=True)
    config_json      = Column(Text, nullable=False)
    total_folds      = Column(Integer, nullable=False)
    robust_signals_json  = Column(Text, default="[]")
    overfit_signals_json = Column(Text, default="[]")
    status           = Column(String(20), default="pending")
    execution_time_s = Column(Float, default=0.0)
    error_message    = Column(Text)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    folds = relationship(
        "WalkForwardFoldRecord", back_populates="run", cascade="all, delete-orphan",
    )


class WalkForwardFoldRecord(Base):
    """A single train/test temporal fold within a run."""
    __tablename__ = "walk_forward_folds"
    __table_args__ = (
        Index("idx_wf_folds_run", "run_id", "fold_index"),
    )

    id               = Column(Integer, primary_key=True, autoincrement=True)
    run_id           = Column(String(36), ForeignKey("walk_forward_runs.run_id"), nullable=False)
    fold_index       = Column(Integer, nullable=False)
    train_start      = Column(String(10), nullable=False)
    train_end        = Column(String(10), nullable=False)
    test_start       = Column(String(10), nullable=False)
    test_end         = Column(String(10), nullable=False)

    # Relationships
    run     = relationship("WalkForwardRunRecord", back_populates="folds")
    results = relationship(
        "WalkForwardSignalResultRecord", back_populates="fold", cascade="all, delete-orphan",
    )


class WalkForwardSignalResultRecord(Base):
    """Per-signal IS/OOS metrics for a single fold."""
    __tablename__ = "walk_forward_signal_results"
    __table_args__ = (
        Index("idx_wf_results_signal", "signal_id", "fold_id"),
        Index("idx_wf_results_fold", "fold_id"),
    )

    id               = Column(Integer, primary_key=True, autoincrement=True)
    fold_id          = Column(Integer, ForeignKey("walk_forward_folds.id"), nullable=False)
    signal_id        = Column(String(50), nullable=False, index=True)
    signal_name      = Column(String(100))
    # IS metrics
    is_hit_rate      = Column(Float)
    is_sharpe        = Column(Float)
    is_alpha         = Column(Float)
    is_firings       = Column(Integer, default=0)
    qualified        = Column(Boolean, default=False)
    # OOS metrics
    oos_hit_rate     = Column(Float)
    oos_sharpe       = Column(Float)
    oos_alpha        = Column(Float)
    oos_firings      = Column(Integer, default=0)

    # Relationship
    fold = relationship("WalkForwardFoldRecord", back_populates="results")


# ─── Transaction Cost Model Tables ───────────────────────────────────────────

class CostModelProfileRecord(Base):
    """Per-signal cost analysis results from a backtest run."""
    __tablename__ = "cost_model_profiles"
    __table_args__ = (
        Index("idx_cost_signal_run", "signal_id", "run_id"),
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    run_id              = Column(String(36), nullable=False, index=True)
    signal_id           = Column(String(50), nullable=False, index=True)
    signal_name         = Column(String(100))
    raw_sharpe_20       = Column(Float)
    adjusted_sharpe_20  = Column(Float)
    raw_alpha_20        = Column(Float)
    net_alpha_20        = Column(Float)
    avg_total_cost      = Column(Float)
    cost_drag_bps       = Column(Float)
    breakeven_cost_bps  = Column(Float)
    cost_resilience     = Column(Float)
    cost_adjusted_tier  = Column(String(2))
    created_at          = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Benchmark & Factor Evaluation Tables ─────────────────────────────────────

class BenchmarkFactorProfileRecord(Base):
    """Per-signal benchmark & factor evaluation results."""
    __tablename__ = "benchmark_factor_profiles"
    __table_args__ = (
        Index("idx_bf_signal_run", "signal_id", "run_id"),
    )

    id                = Column(Integer, primary_key=True, autoincrement=True)
    run_id            = Column(String(36), nullable=False, index=True)
    signal_id         = Column(String(50), nullable=False, index=True)
    signal_name       = Column(String(100))
    excess_vs_market  = Column(Float)
    ir_vs_market      = Column(Float)
    excess_vs_sector  = Column(Float)
    ir_vs_sector      = Column(Float)
    factor_alpha      = Column(Float)
    alpha_t_stat      = Column(Float)
    alpha_significant = Column(Boolean, default=False)
    beta_market       = Column(Float)
    beta_size         = Column(Float)
    beta_value        = Column(Float)
    beta_momentum     = Column(Float)
    r_squared         = Column(Float)
    factor_neutrality = Column(Float)
    alpha_source      = Column(String(20))
    n_observations    = Column(Integer, default=0)
    created_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Signal Redundancy Tables ────────────────────────────────────────────────

class SignalRedundancyRecord(Base):
    """Per-signal redundancy analysis results."""
    __tablename__ = "signal_redundancy_profiles"
    __table_args__ = (
        Index("idx_red_signal_run", "signal_id", "run_id"),
    )

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    run_id             = Column(String(36), nullable=False, index=True)
    signal_id          = Column(String(50), nullable=False, index=True)
    signal_name        = Column(String(100))
    max_correlation    = Column(Float)
    max_corr_partner   = Column(String(50))
    max_mi             = Column(Float)
    incremental_alpha  = Column(Float)
    redundancy_score   = Column(Float)
    classification     = Column(String(20))
    recommended_weight = Column(Float)
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Regime Weight Tables ────────────────────────────────────────────────────

class RegimeWeightRecord(Base):
    """Per-signal regime-adaptive weight profiles."""
    __tablename__ = "regime_weight_profiles"
    __table_args__ = (
        Index("idx_rw_signal_run", "signal_id", "run_id"),
    )

    id                = Column(Integer, primary_key=True, autoincrement=True)
    run_id            = Column(String(36), nullable=False, index=True)
    signal_id         = Column(String(50), nullable=False, index=True)
    signal_name       = Column(String(100))
    current_regime    = Column(String(20))
    base_weight       = Column(Float)
    regime_multiplier = Column(Float)
    effective_weight  = Column(Float)
    best_regime       = Column(String(20))
    worst_regime      = Column(String(20))
    regime_stats_json = Column(Text)
    created_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Signal Ensemble Tables ──────────────────────────────────────────────────

class SignalEnsembleRecord(Base):
    """Discovered signal ensemble combinations."""
    __tablename__ = "signal_ensemble_profiles"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    run_id          = Column(String(36), nullable=False, index=True)
    signal_ids_json = Column(Text)
    co_fire_count   = Column(Integer)
    synergy_score   = Column(Float)
    stability       = Column(Float)
    ensemble_score  = Column(Float)
    joint_sharpe    = Column(Float)
    joint_hit_rate  = Column(Float)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Meta-Learning Tables ────────────────────────────────────────────────────

class MetaLearningRecord(Base):
    """Meta-learning recommendations."""
    __tablename__ = "meta_learning_recommendations"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    run_id          = Column(String(36), nullable=False, index=True)
    target_id       = Column(String(50), nullable=False, index=True)
    target_name     = Column(String(100))
    recommendation  = Column(String(30))
    reason          = Column(Text)
    current_value   = Column(Float)
    suggested_value = Column(Float)
    confidence      = Column(Float)
    priority        = Column(Integer)
    applied         = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Concept Drift Tables ────────────────────────────────────────────────────

class ConceptDriftRecord(Base):
    """Concept drift detection alerts."""
    __tablename__ = "concept_drift_alerts"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    run_id             = Column(String(36), nullable=False, index=True)
    signal_id          = Column(String(50), nullable=False, index=True)
    severity           = Column(String(20))
    active_detectors   = Column(Integer)
    drift_score        = Column(Float)
    detections_json    = Column(Text)
    recommended_action = Column(String(30))
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Online Learning Tables ──────────────────────────────────────────────────

class OnlineLearningRecord(Base):
    """Online learning weight updates."""
    __tablename__ = "online_learning_updates"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    run_id             = Column(String(36), nullable=False, index=True)
    signal_id          = Column(String(50), nullable=False, index=True)
    weight_before      = Column(Float)
    weight_after       = Column(Float)
    delta              = Column(Float)
    raw_delta          = Column(Float)
    dampened           = Column(Boolean, default=False)
    observation_return = Column(Float)
    learning_rate_used = Column(Float)
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Signal Discovery Tables ─────────────────────────────────────────────────

class SignalCandidateRecord(Base):
    """Discovered signal candidates."""
    __tablename__ = "signal_candidates"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    run_id                  = Column(String(36), nullable=False, index=True)
    candidate_id            = Column(String(50), nullable=False, index=True)
    name                    = Column(String(100))
    feature_formula         = Column(String(200))
    direction               = Column(String(10))
    threshold               = Column(Float)
    category                = Column(String(20))
    information_coefficient = Column(Float)
    hit_rate                = Column(Float)
    sharpe_ratio            = Column(Float)
    sample_size             = Column(Integer)
    stability               = Column(Float)
    p_value                 = Column(Float)
    adjusted_p_value        = Column(Float)
    status                  = Column(String(20))
    created_at              = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Allocation Learning Tables ──────────────────────────────────────────────

class AllocationLearningRecord(Base):
    """Allocation learning outcomes."""
    __tablename__ = "allocation_learning_outcomes"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    run_id          = Column(String(36), nullable=False, index=True)
    ticker          = Column(String(10))
    bucket_id       = Column(String(20), index=True)
    allocation_pct  = Column(Float)
    forward_return  = Column(Float)
    reward          = Column(Float)
    ucb_score       = Column(Float)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Research Governance Tables ──────────────────────────────────────────────

class ExperimentRecord(Base):
    """Registry of all research experiments for institutional reproducibility."""
    __tablename__ = "experiments"
    __table_args__ = (
        Index("idx_experiments_type_status", "experiment_type", "status"),
        Index("idx_experiments_parent", "parent_experiment_id"),
    )

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id         = Column(String(36), nullable=False, unique=True, index=True)
    experiment_type       = Column(String(30), nullable=False)  # backtest|walk_forward|discovery|calibration|ensemble|online_learning
    name                  = Column(String(200), nullable=False)
    config_snapshot_json  = Column(Text, default="{}")           # Frozen config at run time
    signal_versions_json  = Column(Text, default="{}")           # Snapshot of signal weights/thresholds
    parent_experiment_id  = Column(String(36), nullable=True)    # Lineage: FK conceptual
    status                = Column(String(20), default="pending")
    metrics_json          = Column(Text, default="{}")           # Results summary
    error_message         = Column(Text)
    created_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at          = Column(DateTime)
    created_by            = Column(String(30), default="auto")   # auto|manual|scheduler

    artifacts = relationship(
        "ExperimentArtifactRecord", back_populates="experiment",
        cascade="all, delete-orphan",
    )


class ExperimentArtifactRecord(Base):
    """Artifacts produced by an experiment (weights, reports, configs…)."""
    __tablename__ = "experiment_artifacts"
    __table_args__ = (
        Index("idx_exp_artifacts_experiment", "experiment_id"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id   = Column(String(36), ForeignKey("experiments.experiment_id"), nullable=False)
    artifact_type   = Column(String(30), nullable=False)         # weights|thresholds|model_params|report|config|metrics
    artifact_json   = Column(Text, nullable=False)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    experiment = relationship("ExperimentRecord", back_populates="artifacts")


class SignalVersionRecord(Base):
    """Immutable version history of signal configurations."""
    __tablename__ = "signal_versions"
    __table_args__ = (
        Index("idx_signal_versions_signal", "signal_id", "version_number"),
        Index("idx_signal_versions_active", "signal_id", "effective_until"),
    )

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    signal_id               = Column(String(64), nullable=False, index=True)
    version_number          = Column(Integer, nullable=False)
    config_json             = Column(Text, nullable=False)       # threshold, weight, half_life, enabled, …
    effective_from          = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    effective_until         = Column(DateTime)                    # NULL = currently active
    produced_by_experiment  = Column(String(36))                  # FK conceptual → experiments.experiment_id
    created_at              = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GovernanceAuditRecord(Base):
    """Immutable, append-only audit trail for governance events."""
    __tablename__ = "governance_audit"
    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_action", "action", "timestamp"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    action        = Column(String(40), nullable=False)           # experiment_created|weight_updated|…
    entity_type   = Column(String(30), nullable=False)           # experiment|signal|weight|threshold
    entity_id     = Column(String(64), nullable=False)
    details_json  = Column(Text, default="{}")
    performed_by  = Column(String(30), default="auto")
    timestamp     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ─── Live Performance Scorecard Tables ───────────────────────────────────────

class LiveSignalTrackingRecord(Base):
    """Tracks live signal fires with forward returns for P&L attribution."""
    __tablename__ = "live_signal_tracking"
    __table_args__ = (
        Index("idx_live_tracking_signal", "signal_id", "fired_at"),
        Index("idx_live_tracking_ticker", "ticker", "fired_at"),
        Index("idx_live_tracking_complete", "tracking_complete", "fired_at"),
    )

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    signal_id          = Column(String(64), nullable=False, index=True)
    signal_name        = Column(String(100))
    category           = Column(String(20))
    ticker             = Column(String(16), nullable=False, index=True)
    strength           = Column(String(10))                  # strong|moderate|weak
    confidence         = Column(Float, default=0.0)
    entry_price        = Column(Float)
    fired_at           = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    # Forward returns (filled asynchronously)
    return_1d          = Column(Float)
    return_5d          = Column(Float)
    return_20d         = Column(Float)
    return_60d         = Column(Float)
    # Benchmark returns for excess calculation
    benchmark_return_1d  = Column(Float)
    benchmark_return_5d  = Column(Float)
    benchmark_return_20d = Column(Float)
    benchmark_return_60d = Column(Float)
    # Tracking state
    tracking_complete  = Column(Boolean, default=False)
    last_updated       = Column(DateTime)


# ─── Shadow Portfolio Tables ─────────────────────────────────────────────────

class ShadowPortfolioRecord(Base):
    """Persistent simulation portfolios."""
    __tablename__ = "shadow_portfolios"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id    = Column(String(36), nullable=False, unique=True, index=True)
    name            = Column(String(200), nullable=False)
    portfolio_type  = Column(String(20), nullable=False)     # research|benchmark|strategy
    strategy_id     = Column(String(36))                     # FK conceptual → strategies
    config_json     = Column(Text, default="{}")
    inception_date  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ShadowPositionRecord(Base):
    """Individual positions within a shadow portfolio."""
    __tablename__ = "shadow_positions"
    __table_args__ = (
        Index("idx_shadow_pos_portfolio", "portfolio_id", "exit_date"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id    = Column(String(36), nullable=False, index=True)
    ticker          = Column(String(16), nullable=False)
    weight          = Column(Float, nullable=False)
    entry_price     = Column(Float, nullable=False)
    entry_date      = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    exit_price      = Column(Float)
    exit_date       = Column(DateTime)
    sizing_method   = Column(String(20), default="vol_parity")


class ShadowSnapshotRecord(Base):
    """Daily NAV snapshots for performance tracking."""
    __tablename__ = "shadow_snapshots"
    __table_args__ = (
        Index("idx_shadow_snap_portfolio", "portfolio_id", "snapshot_date"),
    )

    id                = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id      = Column(String(36), nullable=False, index=True)
    snapshot_date     = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    nav               = Column(Float, nullable=False, default=100.0)
    daily_return      = Column(Float, default=0.0)
    cumulative_return = Column(Float, default=0.0)
    drawdown          = Column(Float, default=0.0)
    positions_count   = Column(Integer, default=0)
    positions_json    = Column(Text)                          # Full state snapshot


# ─── Strategy Layer Tables ───────────────────────────────────────────────────

class StrategyRecord(Base):
    """Named investment strategies combining signals + rules."""
    __tablename__ = "strategies"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id     = Column(String(36), nullable=False, unique=True, index=True)
    name            = Column(String(200), nullable=False)
    description     = Column(Text)
    config_json     = Column(Text, nullable=False)              # Full StrategyConfig JSON
    version         = Column(String(20), default="1.0.0")       # Semver
    lifecycle_state = Column(String(20), default="draft")       # draft|research|backtested|validated|paper|live|paused|retired
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime)
    created_by      = Column(String(30), default="manual")


# ─── Liquidity & Capacity Tables ─────────────────────────────────────────────

class LiquidityProfileRecord(Base):
    """Per-ticker liquidity and capacity estimates."""
    __tablename__ = "liquidity_profiles"
    __table_args__ = (
        Index("idx_liquidity_ticker", "ticker", "updated_at"),
    )

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    ticker                   = Column(String(16), nullable=False, index=True)
    avg_daily_volume_20d     = Column(Float)
    avg_spread_bps           = Column(Float)
    market_cap               = Column(Float)
    estimated_impact_1pct    = Column(Float)                  # Cost for 1% participation
    estimated_capacity_usd   = Column(Float)                  # Max investable size
    turnover_annual          = Column(Float)
    liquidity_tier           = Column(String(20))             # high|medium|low|illiquid
    updated_at               = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Pilot Deployment Tables ─────────────────────────────────────────────────

class PilotRunRecord(Base):
    """Master record for a pilot deployment run."""
    __tablename__ = "pilot_runs"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    pilot_id     = Column(String(36), nullable=False, unique=True, index=True)
    phase        = Column(String(20), nullable=False, default="setup")  # setup|observation|paper_trading|evaluation|completed
    week         = Column(Integer, default=0)
    start_date   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    end_date     = Column(DateTime)
    config_json  = Column(Text, default="{}")    # Portfolio IDs, counters, settings
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PilotDailySnapshotRecord(Base):
    """Daily portfolio snapshot for pilot performance tracking."""
    __tablename__ = "pilot_daily_snapshots"
    __table_args__ = (
        Index("idx_pilot_snap_portfolio", "pilot_id", "portfolio_id", "snapshot_date"),
    )

    id                = Column(Integer, primary_key=True, autoincrement=True)
    pilot_id          = Column(String(36), nullable=False, index=True)
    portfolio_id      = Column(String(36), nullable=False, index=True)
    snapshot_date     = Column(DateTime, nullable=False)
    nav               = Column(Float, default=1000000.0)
    daily_return      = Column(Float, default=0.0)
    cumulative_return = Column(Float, default=0.0)
    drawdown          = Column(Float, default=0.0)
    positions_count   = Column(Integer, default=0)
    signal_count      = Column(Integer, default=0)
    metrics_json      = Column(Text, default="{}")


class PilotAlertRecord(Base):
    """Persistent record of pilot alerts and their actions."""
    __tablename__ = "pilot_alerts"
    __table_args__ = (
        Index("idx_pilot_alert_type", "pilot_id", "alert_type", "created_at"),
    )

    id           = Column(Integer, primary_key=True, autoincrement=True)
    alert_id     = Column(String(36), nullable=False, index=True)
    pilot_id     = Column(String(36), nullable=False, index=True)
    alert_type   = Column(String(40), nullable=False)
    severity     = Column(String(20), nullable=False)
    portfolio_id = Column(String(36))
    message      = Column(Text)
    auto_action  = Column(String(40))
    resolved     = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PilotMetricRecord(Base):
    """Rolling pilot metrics store."""
    __tablename__ = "pilot_metrics"
    __table_args__ = (
        Index("idx_pilot_metric_type", "pilot_id", "metric_type", "computed_at"),
    )

    id           = Column(Integer, primary_key=True, autoincrement=True)
    pilot_id     = Column(String(36), nullable=False, index=True)
    metric_type  = Column(String(30), nullable=False)   # signal|idea|strategy|portfolio|system
    metric_name  = Column(String(50), nullable=False)
    value        = Column(Float, default=0.0)
    category     = Column(String(30))                    # signal category, strategy id, portfolio type
    computed_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Create tables ────────────────────────────────────────────────────────────

def init_db():
    """Call once at startup to create all tables and declarative indexes."""
    Base.metadata.create_all(ENGINE)
    db_type = "PostgreSQL" if "postgresql" in str(ENGINE.url) else "SQLite"
    print(f"[DB] Database initialised ({db_type}) — {ENGINE.url.database}")


# ─── DB-backed Fundamental Cache ──────────────────────────────────────────────

class FundamentalDBCache:
    """
    Drop-in replacement for the in-memory FundamentalCache.
    Persists results to SQLite so they survive server restarts.
    TTL: 24 hours
    """
    TTL = 86_400  # seconds

    def get(self, ticker: str) -> dict | None:
        symbol = ticker.upper()
        now = time.time()
        with SessionLocal() as db:
            row = (
                db.query(FundamentalAnalysis)
                .filter(
                    FundamentalAnalysis.ticker == symbol,
                    FundamentalAnalysis.expires_at > now,
                )
                .order_by(FundamentalAnalysis.analyzed_at.desc())
                .first()
            )
            if not row:
                return None
            print(f"[FUND-DB-CACHE] HIT for {symbol}")
            return self._row_to_events(row)

    def set(self, ticker: str, data: dict):
        """data = {events: [...]} — the same format as in-memory cache."""
        symbol = ticker.upper()
        events = data.get("events", [])
        expires = time.time() + self.TTL

        # Extract key fields from events for indexed columns
        committee = next(
            (e["data"] for e in events if e["event"] == "committee_verdict"), {}
        )
        data_ready = next(
            (e["data"] for e in events if e["event"] == "data_ready"), {}
        )
        agent_memos = [e["data"] for e in events if e["event"] == "agent_memo"]
        research = next(
            (e["data"].get("memo", "") for e in events if e["event"] == "research_memo"), ""
        )

        row = FundamentalAnalysis(
            ticker=symbol,
            signal=committee.get("signal"),
            score=committee.get("score"),
            confidence=committee.get("confidence"),
            risk_adj_score=committee.get("risk_adjusted_score"),
            allocation=committee.get("allocation_recommendation"),
            committee_json=json.dumps(committee),
            agent_memos_json=json.dumps(agent_memos),
            ratios_json=json.dumps(data_ready.get("ratios", {})),
            research_memo=research,
            expires_at=expires,
        )

        with SessionLocal() as db:
            db.add(row)
            db.commit()
            # Append to score history
            if committee.get("score") is not None:
                db.add(ScoreHistory(
                    ticker=symbol,
                    analysis_type="fundamental",
                    score=committee["score"],
                    signal=committee.get("signal"),
                ))
                db.commit()

        print(f"[FUND-DB-CACHE] Stored {symbol} (TTL {self.TTL}s, expires {datetime.fromtimestamp(expires).isoformat()})")

    def invalidate(self, ticker: str) -> bool:
        symbol = ticker.upper()
        with SessionLocal() as db:
            deleted = (
                db.query(FundamentalAnalysis)
                .filter(FundamentalAnalysis.ticker == symbol)
                .delete()
            )
            db.commit()
        return deleted > 0

    def status(self) -> list[dict]:
        now = time.time()
        with SessionLocal() as db:
            rows = (
                db.query(FundamentalAnalysis)
                .filter(FundamentalAnalysis.expires_at > now)
                .all()
            )
            return [
                {
                    "ticker": r.ticker,
                    "signal": r.signal,
                    "score": r.score,
                    "age_s": round(now - r.analyzed_at.timestamp()) if r.analyzed_at else None,
                    "expires_in_s": round(r.expires_at - now),
                }
                for r in rows
            ]

    @staticmethod
    def _row_to_events(row: FundamentalAnalysis) -> dict:
        """Reconstruct the events list from a DB row."""
        events = []
        try:
            ratios = json.loads(row.ratios_json or "{}")
            events.append({"event": "data_ready", "data": {"ticker": row.ticker, "ratios": ratios}})
        except Exception:
            pass

        try:
            memos = json.loads(row.agent_memos_json or "[]")
            for m in memos:
                events.append({"event": "agent_memo", "data": m})
        except Exception:
            pass

        try:
            committee = json.loads(row.committee_json or "{}")
            events.append({"event": "committee_verdict", "data": committee})
        except Exception:
            pass

        if row.research_memo:
            events.append({"event": "research_memo", "data": {"memo": row.research_memo}})

        return {"events": events}


# ─── DB-backed Technical Cache ────────────────────────────────────────────────

class TechnicalDBCache:
    """
    Drop-in replacement for in-memory TechnicalCache.
    TTL: 15 minutes
    """
    TTL = 900  # seconds

    def get(self, ticker: str) -> dict | None:
        symbol = ticker.upper()
        now = time.time()
        with SessionLocal() as db:
            row = (
                db.query(TechnicalAnalysis)
                .filter(
                    TechnicalAnalysis.ticker == symbol,
                    TechnicalAnalysis.expires_at > now,
                )
                .order_by(TechnicalAnalysis.analyzed_at.desc())
                .first()
            )
            if not row:
                return None
            print(f"[TECH-DB-CACHE] HIT for {symbol}")
            try:
                return json.loads(row.summary_json or "{}")
            except Exception:
                return None

    def set(self, ticker: str, data: dict):
        symbol = ticker.upper()
        expires = time.time() + self.TTL
        summary = data.get("summary", {})

        row = TechnicalAnalysis(
            ticker=symbol,
            signal=summary.get("signal"),
            technical_score=summary.get("technical_score"),
            trend_status=summary.get("trend_status"),
            momentum_status=summary.get("momentum_status"),
            signal_strength=summary.get("signal_strength"),
            summary_json=json.dumps(data),
            indicators_json=json.dumps(data.get("indicators", {})),
            expires_at=expires,
        )

        with SessionLocal() as db:
            db.add(row)
            db.commit()
            # Append to score history
            score = summary.get("technical_score")
            if score is not None:
                db.add(ScoreHistory(
                    ticker=symbol,
                    analysis_type="technical",
                    score=score,
                    signal=summary.get("signal"),
                ))
                db.commit()

        print(f"[TECH-DB-CACHE] Stored {symbol} (TTL {self.TTL}s)")

    def invalidate(self, ticker: str) -> bool:
        symbol = ticker.upper()
        with SessionLocal() as db:
            deleted = (
                db.query(TechnicalAnalysis)
                .filter(TechnicalAnalysis.ticker == symbol)
                .delete()
            )
            db.commit()
        return deleted > 0

    def status(self) -> list[dict]:
        now = time.time()
        with SessionLocal() as db:
            rows = (
                db.query(TechnicalAnalysis)
                .filter(TechnicalAnalysis.expires_at > now)
                .all()
            )
            return [
                {
                    "ticker": r.ticker,
                    "signal": r.signal,
                    "score": r.technical_score,
                    "age_s": round(now - r.analyzed_at.timestamp()) if r.analyzed_at else None,
                    "expires_in_s": round(r.expires_at - now),
                }
                for r in rows
            ]


# ─── Score History Queries ────────────────────────────────────────────────────

def get_score_history(ticker: str, analysis_type: str, limit: int = 90) -> list[dict]:
    """Return the last N score records for a ticker + analysis type."""
    symbol = ticker.upper()
    with SessionLocal() as db:
        rows = (
            db.query(ScoreHistory)
            .filter(
                ScoreHistory.ticker == symbol,
                ScoreHistory.analysis_type == analysis_type,
            )
            .order_by(ScoreHistory.recorded_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
                "score": row.score,
                "signal": row.signal,
            }
            for row in reversed(rows)
        ]
