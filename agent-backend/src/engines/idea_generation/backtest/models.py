"""
src/engines/idea_generation/backtest/models.py
──────────────────────────────────────────────────────────────────────────────
Data models for the IDEA Backtesting + Calibration layer.

Contains:
  - Pydantic contracts (IdeaSnapshot, OutcomeResult, analytics DTOs)
  - Enumerations (EvaluationHorizon, OutcomeLabel)
  - Configuration (HitPolicy, BacktestConfig)
  - SQLAlchemy ORM models (IdeaSnapshotRecord, SnapshotOutcomeRecord)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


# ─── Enumerations ─────────────────────────────────────────────────────────────


class EvaluationHorizon(str, Enum):
    """Horizons for ex-post evaluation (business-day approximated)."""
    H1D = "1D"
    H5D = "5D"
    H20D = "20D"
    H60D = "60D"

    @property
    def calendar_days(self) -> int:
        """Approximate calendar days for each horizon."""
        return {"1D": 1, "5D": 7, "20D": 30, "60D": 90}[self.value]


class OutcomeLabel(str, Enum):
    WIN = "win"
    NEUTRAL = "neutral"
    LOSS = "loss"


# ─── Configuration ────────────────────────────────────────────────────────────


class HitPolicy(BaseModel):
    """Configurable definition of what constitutes a 'hit'."""
    mode: str = Field(
        "return_above_threshold",
        description="Hit determination mode: return_above_threshold | excess_above_threshold",
    )
    threshold: float = Field(
        0.0,
        description="Minimum return to qualify as a hit (e.g. 0.0 = any positive return)",
    )
    neutral_band: float = Field(
        0.005,
        description="Returns within ±neutral_band are classified as NEUTRAL",
    )

    def classify(self, raw_return: float | None, excess_return: float | None = None) -> OutcomeLabel:
        """Classify an outcome based on the policy."""
        if raw_return is None:
            return OutcomeLabel.NEUTRAL

        check_value = raw_return
        if self.mode == "excess_above_threshold" and excess_return is not None:
            check_value = excess_return

        if check_value > self.threshold + self.neutral_band:
            return OutcomeLabel.WIN
        elif check_value < self.threshold - self.neutral_band:
            return OutcomeLabel.LOSS
        return OutcomeLabel.NEUTRAL

    def is_hit(self, raw_return: float | None, excess_return: float | None = None) -> bool:
        return self.classify(raw_return, excess_return) == OutcomeLabel.WIN


class BacktestConfig(BaseModel):
    """Configuration for the backtest layer."""
    snapshot_enabled: bool = Field(True, description="Whether to capture snapshots on scan")
    horizons: list[EvaluationHorizon] = Field(
        default_factory=lambda: list(EvaluationHorizon),
        description="Horizons to evaluate",
    )
    hit_policy: HitPolicy = Field(default_factory=HitPolicy)
    benchmark_ticker: str | None = Field(None, description="Benchmark ticker for excess returns")


# ─── IdeaSnapshot (Pydantic DTO) ─────────────────────────────────────────────


class IdeaSnapshot(BaseModel):
    """Auditable snapshot of an idea at the moment of generation.

    This is the core unit of backtesting — it captures everything needed
    to evaluate the idea ex-post without depending on live entities.
    """
    snapshot_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Identity ──
    scan_id: str | None = None
    ticker: str
    detector: str = ""
    idea_type: str = ""
    source: str = "legacy"

    # ── Scoring dimensions ──
    signal_strength: float = 0.0
    confidence_score: float = 0.0
    alpha_score: float = 0.0
    rank_score: float = 0.0

    # ── Signal counts ──
    active_signals_count: int = 0
    strong_signals_count: int = 0
    moderate_signals_count: int = 0
    weak_signals_count: int = 0

    # ── Context ──
    rationale: str = ""
    scan_mode: str = "local"
    strategy_profile: str | None = None
    registry_key: str = ""
    name: str = ""
    sector: str = ""
    confidence_level: str = "medium"

    # ── Market context ──
    price_at_signal: float | None = None
    market_metadata: dict = Field(default_factory=dict)


# ─── OutcomeResult (Pydantic DTO) ────────────────────────────────────────────


class OutcomeResult(BaseModel):
    """Result of evaluating a snapshot at a specific horizon."""
    snapshot_id: str
    horizon: EvaluationHorizon
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Prices ──
    price_at_signal: float | None = None
    price_at_horizon: float | None = None

    # ── Returns ──
    raw_return: float | None = None
    excess_return: float | None = None

    # ── Excursion (optional) ──
    max_favorable_excursion: float | None = None
    max_adverse_excursion: float | None = None
    drawdown_from_signal: float | None = None

    # ── Classification ──
    is_hit: bool = False
    outcome_label: OutcomeLabel = OutcomeLabel.NEUTRAL

    # ── Data quality ──
    data_available: bool = True


# ─── Analytics DTOs ──────────────────────────────────────────────────────────


class GroupMetrics(BaseModel):
    """Aggregated metrics for a group of snapshots."""
    group_key: str
    group_value: str
    horizon: str = ""

    total_ideas: int = 0
    total_evaluated: int = 0
    hit_rate: float = 0.0
    average_return: float = 0.0
    median_return: float = 0.0
    average_excess_return: float = 0.0
    win_loss_ratio: float = 0.0
    average_confidence: float = 0.0
    average_alpha_score: float = 0.0
    average_signal_strength: float = 0.0
    false_positive_rate: float = 0.0
    coverage_ratio: float = 0.0


class CalibrationBucket(BaseModel):
    """Calibration data for a single confidence bucket."""
    bucket_label: str
    bucket_min: float
    bucket_max: float
    total_count: int = 0
    hit_count: int = 0
    observed_hit_rate: float = 0.0
    average_return: float = 0.0
    average_confidence: float = 0.0
    calibration_gap: float = 0.0


class CalibrationReport(BaseModel):
    """Full calibration summary."""
    buckets: list[CalibrationBucket] = Field(default_factory=list)
    overall_calibration_error: float = 0.0
    is_monotonic: bool = False
    monotonicity_violations: list[str] = Field(default_factory=list)
    total_evaluated: int = 0
    horizon: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecayPoint(BaseModel):
    """Performance at a single horizon for decay analysis."""
    horizon: str
    average_return: float = 0.0
    hit_rate: float = 0.0
    sample_count: int = 0


class DecayProfile(BaseModel):
    """Alpha decay analysis for a detector or group."""
    group_key: str
    group_value: str
    points: list[DecayPoint] = Field(default_factory=list)
    best_horizon: str = ""
    decay_detected: bool = False
    decay_description: str = ""


# ─── SQLAlchemy ORM Models ───────────────────────────────────────────────────

from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Boolean, Index
from src.data.database import Base


class IdeaSnapshotRecord(Base):
    """Persistent snapshot of an idea for backtesting."""
    __tablename__ = "idea_snapshots"
    __table_args__ = (
        Index("idx_snapshots_ticker_date", "ticker", "generated_at"),
        Index("idx_snapshots_detector", "detector", "idea_type", "generated_at"),
        Index("idx_snapshots_eval_status", "evaluation_status", "generated_at"),
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id         = Column(String(16), nullable=False, unique=True, index=True)
    generated_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Identity
    scan_id             = Column(String(20))
    ticker              = Column(String(16), nullable=False, index=True)
    detector            = Column(String(30), nullable=False, default="")
    idea_type           = Column(String(20), nullable=False, default="")
    source              = Column(String(30), default="legacy")

    # Scoring
    signal_strength     = Column(Float, nullable=False, default=0.0)
    confidence_score    = Column(Float, nullable=False, default=0.0)
    alpha_score         = Column(Float, default=0.0)
    rank_score          = Column(Float, default=0.0)

    # Signal counts
    active_signals_count    = Column(Integer, default=0)
    strong_signals_count    = Column(Integer, default=0)
    moderate_signals_count  = Column(Integer, default=0)
    weak_signals_count      = Column(Integer, default=0)

    # Context
    rationale           = Column(Text, default="")
    scan_mode           = Column(String(20), default="local")
    strategy_profile    = Column(String(50))
    registry_key        = Column(String(30), default="")
    name                = Column(String(200), default="")
    sector              = Column(String(100), default="")
    confidence_level    = Column(String(10), default="medium")

    # Market context
    price_at_signal     = Column(Float)
    market_metadata_json = Column(Text, default="{}")

    # Lifecycle
    evaluation_status   = Column(String(20), default="pending")  # pending|partial|complete


class SnapshotOutcomeRecord(Base):
    """Persisted outcome evaluation for a snapshot at a specific horizon."""
    __tablename__ = "snapshot_outcomes"
    __table_args__ = (
        Index("idx_outcomes_snapshot", "snapshot_id", "horizon"),
        Index("idx_outcomes_detector", "detector", "horizon", "outcome_label"),
    )

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id             = Column(String(16), nullable=False, index=True)
    horizon                 = Column(String(5), nullable=False)  # 1D|5D|20D|60D
    evaluated_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Denormalized for analytics performance
    ticker                  = Column(String(16), nullable=False)
    detector                = Column(String(30), nullable=False, default="")
    idea_type               = Column(String(20), nullable=False, default="")
    confidence_score        = Column(Float, default=0.0)
    signal_strength         = Column(Float, default=0.0)
    alpha_score             = Column(Float, default=0.0)

    # Prices
    price_at_signal         = Column(Float)
    price_at_horizon        = Column(Float)

    # Returns
    raw_return              = Column(Float)
    excess_return           = Column(Float)

    # Excursion
    max_favorable_excursion = Column(Float)
    max_adverse_excursion   = Column(Float)
    drawdown_from_signal    = Column(Float)

    # Classification
    is_hit                  = Column(Boolean, default=False)
    outcome_label           = Column(String(10), default="neutral")

    # Data quality
    data_available          = Column(Boolean, default=True)
