"""
src/data/models/operations.py
─────────────────────────────────────────────────────────────────────────────
Operational models: shadow portfolios, strategies, liquidity, pilot.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Integer, Float, String, Text, DateTime, Index,
)

from src.data.models.base import Base


class ShadowPortfolioRecord(Base):
    __tablename__ = "shadow_portfolios"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id    = Column(String(36), nullable=False, unique=True, index=True)
    name            = Column(String(200), nullable=False)
    portfolio_type  = Column(String(20), nullable=False)
    strategy_id     = Column(String(36))
    config_json     = Column(Text, default="{}")
    inception_date  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ShadowPositionRecord(Base):
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
    positions_json    = Column(Text)


class StrategyRecord(Base):
    __tablename__ = "strategies"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id     = Column(String(36), nullable=False, unique=True, index=True)
    name            = Column(String(200), nullable=False)
    description     = Column(Text)
    config_json     = Column(Text, nullable=False)
    version         = Column(String(20), default="1.0.0")
    lifecycle_state = Column(String(20), default="draft")
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime)
    created_by      = Column(String(30), default="manual")


class LiquidityProfileRecord(Base):
    __tablename__ = "liquidity_profiles"
    __table_args__ = (
        Index("idx_liquidity_ticker", "ticker", "updated_at"),
    )

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    ticker                   = Column(String(16), nullable=False, index=True)
    avg_daily_volume_20d     = Column(Float)
    avg_spread_bps           = Column(Float)
    market_cap               = Column(Float)
    estimated_impact_1pct    = Column(Float)
    estimated_capacity_usd   = Column(Float)
    turnover_annual          = Column(Float)
    liquidity_tier           = Column(String(20))
    updated_at               = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PilotRunRecord(Base):
    __tablename__ = "pilot_runs"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    pilot_id     = Column(String(36), nullable=False, unique=True, index=True)
    phase        = Column(String(20), nullable=False, default="setup")
    week         = Column(Integer, default=0)
    start_date   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    end_date     = Column(DateTime)
    config_json  = Column(Text, default="{}")
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PilotDailySnapshotRecord(Base):
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
    __tablename__ = "pilot_metrics"
    __table_args__ = (
        Index("idx_pilot_metric_type", "pilot_id", "metric_type", "computed_at"),
    )

    id           = Column(Integer, primary_key=True, autoincrement=True)
    pilot_id     = Column(String(36), nullable=False, index=True)
    metric_type  = Column(String(30), nullable=False)
    metric_name  = Column(String(50), nullable=False)
    value        = Column(Float, default=0.0)
    category     = Column(String(30))
    computed_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
