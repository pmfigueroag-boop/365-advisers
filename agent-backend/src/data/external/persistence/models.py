"""
src/data/external/persistence/models.py
──────────────────────────────────────────────────────────────────────────────
SQLAlchemy models for EDPL health and coverage persistence.

Tables:
  - provider_health_snapshots: periodic health state snapshots
  - provider_fetch_logs: per-fetch log records (7-day retention)
  - analysis_coverage: per-analysis coverage reports
  - stale_data_usage: log of stale data consumption
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)

from src.data.database import Base


class ProviderHealthSnapshotRecord(Base):
    """Periodic snapshot of provider health state."""
    __tablename__ = "provider_health_snapshots"
    __table_args__ = (
        Index("idx_health_snapshot_provider", "provider_name", "snapshot_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(50), nullable=False, index=True)
    domain = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False)
    circuit_breaker_state = Column(String(15), default="closed")
    consecutive_failures = Column(Integer, default=0)
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    avg_latency_ms = Column(Float, default=0.0)
    success_rate_24h = Column(Float, default=0.0)
    snapshot_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class ProviderFetchLogRecord(Base):
    """Per-fetch log record for observability and debugging."""
    __tablename__ = "provider_fetch_logs"
    __table_args__ = (
        Index("idx_fetch_log_provider", "provider_name", "fetched_at"),
        Index("idx_fetch_log_ticker", "ticker", "fetched_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(50), nullable=False, index=True)
    domain = Column(String(30), nullable=False)
    ticker = Column(String(20), nullable=True)
    success = Column(Boolean, nullable=False)
    latency_ms = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    cached = Column(Boolean, default=False)
    fields_populated = Column(Integer, nullable=True)
    fields_total = Column(Integer, nullable=True)
    fetched_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class AnalysisCoverageRecord(Base):
    """Per-analysis coverage report for historical tracking."""
    __tablename__ = "analysis_coverage"
    __table_args__ = (
        Index("idx_coverage_ticker", "ticker", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String(36), unique=True, nullable=False, index=True)
    ticker = Column(String(20), nullable=True, index=True)
    completeness_score = Column(Float, default=0.0)
    completeness_label = Column(String(30), default="Unknown")
    sources_json = Column(Text, default="[]")
    messages_json = Column(Text, default="[]")
    partial_domains_json = Column(Text, default="[]")
    unavailable_domains_json = Column(Text, default="[]")
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )


class StaleDataUsageRecord(Base):
    """Log of stale data consumption for auditing."""
    __tablename__ = "stale_data_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String(36), nullable=False, index=True)
    domain = Column(String(30), nullable=False)
    provider_name = Column(String(50), nullable=False)
    stale_age_seconds = Column(Float, default=0.0)
    freshness_label = Column(String(15), default="unknown")
    used_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
