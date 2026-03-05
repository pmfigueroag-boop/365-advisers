"""
src/engines/monitoring/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Opportunity Monitoring Engine.

Defines snapshot, alert, configuration, and result models for the
snapshot-diff monitoring architecture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


# ─── Enumerations ───────────────────────────────────────────────────────────

class AlertType(str, Enum):
    SCORE_SURGE = "score_surge"
    NEW_SIGNAL = "new_signal"
    TIER_CHANGE = "tier_change"
    ALPHA_SHIFT = "alpha_shift"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ─── Configuration ──────────────────────────────────────────────────────────

class MonitoringConfig(BaseModel):
    """Configurable thresholds for monitoring triggers."""
    case_delta_threshold: float = Field(
        10.0, description="Min CASE score delta to trigger alert",
    )
    opp_delta_threshold: float = Field(
        1.5, description="Min Opportunity Score delta to trigger alert",
    )
    new_signal_threshold: int = Field(
        1, ge=1, description="Min new signals to trigger alert",
    )
    alpha_upper_threshold: float = Field(
        60.0, description="CASE threshold for bullish crossover alert",
    )
    alpha_lower_threshold: float = Field(
        40.0, description="CASE threshold for bearish crossunder alert",
    )
    max_alerts_per_ticker: int = Field(
        5, ge=1, description="Max alerts per ticker per scan",
    )


# ─── Snapshot ───────────────────────────────────────────────────────────────

class OpportunitySnapshot(BaseModel):
    """Point-in-time capture of a ticker's scores and signals."""
    ticker: str
    case_score: float = 0.0
    opportunity_score: float = 0.0
    uos: float = 0.0
    tier: str = ""
    fired_signals: list[str] = Field(
        default_factory=list,
        description="Signal IDs that are currently active",
    )
    signal_count: int = 0
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ─── Alert ──────────────────────────────────────────────────────────────────

class OpportunityAlert(BaseModel):
    """A single monitoring alert."""
    id: str = Field(default_factory=lambda: uuid4().hex[:16])
    ticker: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str = ""
    previous_value: float = 0.0
    current_value: float = 0.0
    delta: float = 0.0
    new_signals: list[str] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    read: bool = False


# ─── Result ─────────────────────────────────────────────────────────────────

class MonitoringResult(BaseModel):
    """Complete output of a monitoring scan."""
    alerts: list[OpportunityAlert] = Field(default_factory=list)
    snapshots: dict[str, OpportunitySnapshot] = Field(default_factory=dict)
    tickers_monitored: int = 0
    alerts_generated: int = 0
    scan_duration_ms: float = 0.0
    scanned_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
