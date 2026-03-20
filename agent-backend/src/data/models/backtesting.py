"""
src/data/models/backtesting.py
─────────────────────────────────────────────────────────────────────────────
Backtesting, validation, walk-forward, cost model, benchmark factor,
signal selection, regime weights, and ensemble models.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Integer, Float, String, Text, DateTime,
    Index, ForeignKey,
)
from sqlalchemy.orm import relationship

from src.data.models.base import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    run_id           = Column(String(36), nullable=False, unique=True, index=True)
    universe_json    = Column(Text, nullable=False)
    start_date       = Column(String(10), nullable=False)
    end_date         = Column(String(10), nullable=False)
    signal_count     = Column(Integer, default=0)
    status           = Column(String(20), default="pending")
    execution_time_s = Column(Float, default=0.0)
    config_json      = Column(Text, default="{}")
    calibration_json = Column(Text, default="[]")
    memo_json        = Column(Text, default=None)
    error_message    = Column(Text)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    results          = relationship("BacktestResult", back_populates="run", cascade="all, delete-orphan")


class BacktestResult(Base):
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
    hit_rate_json            = Column(Text, default="{}")
    avg_return_json          = Column(Text, default="{}")
    avg_excess_return_json   = Column(Text, default="{}")
    median_return_json       = Column(Text, default="{}")
    sharpe_json              = Column(Text, default="{}")
    sortino_json             = Column(Text, default="{}")
    max_drawdown             = Column(Float, default=0.0)
    empirical_half_life      = Column(Float)
    optimal_hold_period      = Column(Integer)
    alpha_decay_curve_json   = Column(Text, default="[]")
    t_statistic_json         = Column(Text, default="{}")
    p_value_json             = Column(Text, default="{}")
    confidence_level         = Column(String(10), default="LOW")
    sample_size              = Column(Integer, default=0)
    universe_size            = Column(Integer, default=0)
    date_range               = Column(String(50))
    created_at               = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    run                      = relationship("BacktestRun", back_populates="results")


class RollingPerformanceRecord(Base):
    __tablename__ = "rolling_performance"
    __table_args__ = (
        Index("idx_rolling_perf", "signal_id", "window_days", "as_of_date"),
    )

    id           = Column(Integer, primary_key=True, autoincrement=True)
    signal_id    = Column(String(50), nullable=False, index=True)
    window_days  = Column(Integer, nullable=False)
    as_of_date   = Column(String(10), nullable=False)
    hit_rate     = Column(Float)
    sharpe       = Column(Float)
    avg_return   = Column(Float)
    avg_excess   = Column(Float)
    sample_size  = Column(Integer)
    regime       = Column(String(20))
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OpportunityPerformanceRecord(Base):
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
    opportunity_score    = Column(Float)
    case_score           = Column(Float)
    fundamental_score    = Column(Float)
    technical_score      = Column(Float)
    suggested_alloc      = Column(Float)
    price_at_gen         = Column(Float)
    generated_at         = Column(DateTime, nullable=False)
    return_1d            = Column(Float)
    return_5d            = Column(Float)
    return_20d           = Column(Float)
    return_60d           = Column(Float)
    benchmark_return_20d = Column(Float)
    excess_return_20d    = Column(Float)
    tracking_status      = Column(String(20), default="pending")
    last_updated         = Column(DateTime)


class DegradationAlertRecord(Base):
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
    action_taken    = Column(String(20), default="none")
    detected_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at     = Column(DateTime)


class WalkForwardRunRecord(Base):
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

    folds = relationship(
        "WalkForwardFoldRecord", back_populates="run", cascade="all, delete-orphan",
    )


class WalkForwardFoldRecord(Base):
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

    run     = relationship("WalkForwardRunRecord", back_populates="folds")
    results = relationship(
        "WalkForwardSignalResultRecord", back_populates="fold", cascade="all, delete-orphan",
    )


class WalkForwardSignalResultRecord(Base):
    __tablename__ = "walk_forward_signal_results"
    __table_args__ = (
        Index("idx_wf_results_signal", "signal_id", "fold_id"),
        Index("idx_wf_results_fold", "fold_id"),
    )

    id               = Column(Integer, primary_key=True, autoincrement=True)
    fold_id          = Column(Integer, ForeignKey("walk_forward_folds.id"), nullable=False)
    signal_id        = Column(String(50), nullable=False, index=True)
    signal_name      = Column(String(100))
    is_hit_rate      = Column(Float)
    is_sharpe        = Column(Float)
    is_alpha         = Column(Float)
    is_firings       = Column(Integer, default=0)
    qualified        = Column(Boolean, default=False)
    oos_hit_rate     = Column(Float)
    oos_sharpe       = Column(Float)
    oos_alpha        = Column(Float)
    oos_firings      = Column(Integer, default=0)

    fold = relationship("WalkForwardFoldRecord", back_populates="results")


class CostModelProfileRecord(Base):
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


class BenchmarkFactorProfileRecord(Base):
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


class SignalRedundancyRecord(Base):
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


class RegimeWeightRecord(Base):
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


class SignalEnsembleRecord(Base):
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
