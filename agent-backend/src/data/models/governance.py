"""
src/data/models/governance.py
─────────────────────────────────────────────────────────────────────────────
Research governance models: experiments, artifacts, audit trail,
meta-learning, concept drift, online learning, allocation learning.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Integer, Float, String, Text, DateTime,
    Index, ForeignKey,
)
from sqlalchemy.orm import relationship

from src.data.models.base import Base


class ExperimentRecord(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        Index("idx_experiments_type_status", "experiment_type", "status"),
        Index("idx_experiments_parent", "parent_experiment_id"),
    )

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id         = Column(String(36), nullable=False, unique=True, index=True)
    experiment_type       = Column(String(30), nullable=False)
    name                  = Column(String(200), nullable=False)
    config_snapshot_json  = Column(Text, default="{}")
    signal_versions_json  = Column(Text, default="{}")
    parent_experiment_id  = Column(String(36), nullable=True)
    status                = Column(String(20), default="pending")
    metrics_json          = Column(Text, default="{}")
    error_message         = Column(Text)
    created_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at          = Column(DateTime)
    created_by            = Column(String(30), default="auto")

    artifacts = relationship(
        "ExperimentArtifactRecord", back_populates="experiment",
        cascade="all, delete-orphan",
    )


class ExperimentArtifactRecord(Base):
    __tablename__ = "experiment_artifacts"
    __table_args__ = (
        Index("idx_exp_artifacts_experiment", "experiment_id"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id   = Column(String(36), ForeignKey("experiments.experiment_id"), nullable=False)
    artifact_type   = Column(String(30), nullable=False)
    artifact_json   = Column(Text, nullable=False)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    experiment = relationship("ExperimentRecord", back_populates="artifacts")


class GovernanceAuditRecord(Base):
    __tablename__ = "governance_audit"
    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_action", "action", "timestamp"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    action        = Column(String(40), nullable=False)
    entity_type   = Column(String(30), nullable=False)
    entity_id     = Column(String(64), nullable=False)
    details_json  = Column(Text, default="{}")
    performed_by  = Column(String(30), default="auto")
    timestamp     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class MetaLearningRecord(Base):
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


class ConceptDriftRecord(Base):
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


class OnlineLearningRecord(Base):
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


class AllocationLearningRecord(Base):
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
