"""
src/engines/research_data/models.py
─────────────────────────────────────────────────────────────────────────────
SQLAlchemy models for the Research Dataset Layer.

Tables:
  feature_snapshots         — versioned feature vectors per ticker×date
  signal_history            — historical signal fire/decay records
  research_datasets         — named, versioned research datasets
  research_dataset_members  — tickers within a dataset
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Integer, Float, String, Text, DateTime,
    Index, ForeignKey,
)
from sqlalchemy.orm import relationship

from src.data.database import Base


# ─── Feature Snapshots ───────────────────────────────────────────────────────

class FeatureSnapshotRecord(Base):
    """A point-in-time feature vector for a single ticker on a single date."""
    __tablename__ = "feature_snapshots"
    __table_args__ = (
        Index("idx_feat_snap_ticker_date", "ticker", "snapshot_date", "feature_set"),
        Index("idx_feat_snap_set", "feature_set", "snapshot_date"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    ticker        = Column(String(16), nullable=False, index=True)
    snapshot_date = Column(String(10), nullable=False)             # ISO date YYYY-MM-DD
    feature_set   = Column(String(50), nullable=False)             # "fundamental_v1", "technical_v2"
    version       = Column(String(20), nullable=False, default="1.0.0")
    features_json = Column(Text, nullable=False)                   # JSON dict of feature_name: value
    source_versions_json = Column(Text, default="{}")              # provenance: {source: version}
    row_count     = Column(Integer, default=1)                     # features in this vector
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Signal History ──────────────────────────────────────────────────────────

class SignalHistoryRecord(Base):
    """Historical record of a signal firing for a ticker on a specific date."""
    __tablename__ = "signal_history"
    __table_args__ = (
        Index("idx_sig_hist_ticker_date", "ticker", "fire_date"),
        Index("idx_sig_hist_signal", "signal_id", "fire_date"),
        Index("idx_sig_hist_category", "category", "fire_date"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    signal_id       = Column(String(64), nullable=False, index=True)
    signal_name     = Column(String(100))
    ticker          = Column(String(16), nullable=False, index=True)
    fire_date       = Column(String(10), nullable=False)           # ISO date
    strength        = Column(String(10), nullable=False)           # strong|moderate|weak
    confidence      = Column(Float, default=0.0)
    direction       = Column(String(10), default="long")           # long|short
    category        = Column(String(20), nullable=False)
    value           = Column(Float)                                # feature value at fire
    decay_factor    = Column(Float, default=1.0)                   # 0.0–1.0 from alpha_decay
    half_life_days  = Column(Float, default=30.0)
    price_at_fire   = Column(Float)
    metadata_json   = Column(Text, default="{}")
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Research Datasets ───────────────────────────────────────────────────────

class ResearchDatasetRecord(Base):
    """A named, versioned research dataset definition."""
    __tablename__ = "research_datasets"
    __table_args__ = (
        Index("idx_research_ds_name_ver", "name", "version"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id    = Column(String(36), nullable=False, unique=True, index=True)
    name          = Column(String(100), nullable=False)
    version       = Column(String(20), nullable=False, default="1.0.0")
    description   = Column(Text, default="")
    # Scope
    tickers_json  = Column(Text, nullable=False)                   # JSON list of tickers
    date_start    = Column(String(10), nullable=False)             # ISO date
    date_end      = Column(String(10), nullable=False)
    # Feature configuration
    feature_sets_json = Column(Text, default="[]")                 # JSON list of feature set names
    signals_json      = Column(Text, default="[]")                 # JSON list of signal IDs to include
    # Stats
    ticker_count  = Column(Integer, default=0)
    row_count     = Column(Integer, default=0)
    # Metadata
    tags_json     = Column(Text, default="[]")
    author        = Column(String(50), default="system")
    status        = Column(String(20), default="active")           # active|archived|deprecated
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationship
    members = relationship(
        "ResearchDatasetMemberRecord", back_populates="dataset",
        cascade="all, delete-orphan",
    )


class ResearchDatasetMemberRecord(Base):
    """Ticker membership in a research dataset."""
    __tablename__ = "research_dataset_members"
    __table_args__ = (
        Index("idx_dsm_dataset_ticker", "dataset_id", "ticker"),
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id  = Column(String(36), ForeignKey("research_datasets.dataset_id"), nullable=False)
    ticker      = Column(String(16), nullable=False)
    sector      = Column(String(100), default="")
    market_cap  = Column(Float)
    added_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    dataset = relationship("ResearchDatasetRecord", back_populates="members")
