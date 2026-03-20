"""
src/data/models/signals.py
─────────────────────────────────────────────────────────────────────────────
Signal-related models: snapshots, activations, performance events,
calibration history, live tracking, candidates, versions.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Integer, Float, String, Text, DateTime,
    Index, ForeignKey,
)

from src.data.models.base import Base


class SignalSnapshot(Base):
    __tablename__ = "signal_snapshots"
    __table_args__ = (
        Index("idx_signal_snapshots_ticker", "ticker", "evaluated_at"),
        Index("idx_signal_snapshots_category", "ticker", "category", "evaluated_at"),
    )

    id                = Column(Integer, primary_key=True, autoincrement=True)
    ticker            = Column(String(16), nullable=False, index=True)
    evaluated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    category          = Column(String(20), nullable=False)
    signals_json      = Column(Text, nullable=False)
    composite_strength= Column(Float, nullable=False, default=0.0)
    confidence        = Column(String(10), nullable=False)
    fired_count       = Column(Integer, default=0)
    total_count       = Column(Integer, default=0)
    scan_id           = Column(String(20))


class CompositeAlphaHistory(Base):
    __tablename__ = "composite_alpha_history"
    __table_args__ = (
        Index("idx_composite_alpha_ticker", "ticker", "evaluated_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    score           = Column(Float, nullable=False)
    environment     = Column(String(30), nullable=False)
    subscores_json  = Column(Text, nullable=False)
    active_categories = Column(Integer, default=0)
    conflicts_json  = Column(Text, default="[]")
    evaluated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class SignalActivationRecord(Base):
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


class SignalPerformanceEventRecord(Base):
    __tablename__ = "signal_performance_events"
    __table_args__ = (
        Index("idx_perf_events_signal_ticker", "signal_id", "ticker", "fired_date"),
        Index("idx_perf_events_ticker", "ticker", "fired_date"),
    )

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    signal_id             = Column(String(50), nullable=False, index=True)
    signal_name           = Column(String(100))
    ticker                = Column(String(16), nullable=False, index=True)
    fired_date            = Column(String(10), nullable=False)
    strength              = Column(String(10), nullable=False)
    confidence            = Column(Float, default=0.0)
    value                 = Column(Float)
    price_at_fire         = Column(Float)
    forward_returns_json  = Column(Text, default="{}")
    benchmark_returns_json= Column(Text, default="{}")
    excess_returns_json   = Column(Text, default="{}")
    run_id                = Column(String(36), ForeignKey("backtest_runs.run_id"), index=True)
    created_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SignalCalibrationHistoryRecord(Base):
    __tablename__ = "signal_calibration_history"
    __table_args__ = (
        Index("idx_calibration_signal", "signal_id", "applied_at"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    signal_id     = Column(String(50), nullable=False, index=True)
    parameter     = Column(String(20), nullable=False)
    old_value     = Column(Float, nullable=False)
    new_value     = Column(Float, nullable=False)
    evidence      = Column(Text)
    run_id        = Column(String(36))
    applied_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    applied_by    = Column(String(20), default="auto")


class LiveSignalTrackingRecord(Base):
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
    strength           = Column(String(10))
    confidence         = Column(Float, default=0.0)
    entry_price        = Column(Float)
    fired_at           = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    return_1d          = Column(Float)
    return_5d          = Column(Float)
    return_20d         = Column(Float)
    return_60d         = Column(Float)
    benchmark_return_1d  = Column(Float)
    benchmark_return_5d  = Column(Float)
    benchmark_return_20d = Column(Float)
    benchmark_return_60d = Column(Float)
    tracking_complete  = Column(Boolean, default=False)
    last_updated       = Column(DateTime)


class SignalCandidateRecord(Base):
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


class SignalVersionRecord(Base):
    __tablename__ = "signal_versions"
    __table_args__ = (
        Index("idx_signal_versions_signal", "signal_id", "version_number"),
        Index("idx_signal_versions_active", "signal_id", "effective_until"),
    )

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    signal_id               = Column(String(64), nullable=False, index=True)
    version_number          = Column(Integer, nullable=False)
    config_json             = Column(Text, nullable=False)
    effective_from          = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    effective_until         = Column(DateTime)
    produced_by_experiment  = Column(String(36))
    created_at              = Column(DateTime, default=lambda: datetime.now(timezone.utc))
