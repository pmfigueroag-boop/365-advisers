"""
src/engines/alpha_alerts/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the Alpha Alert System.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class AlertType(str, Enum):
    MACRO_SHIFT = "macro_shift"
    SENTIMENT_SPIKE = "sentiment_spike"
    SENTIMENT_PANIC = "sentiment_panic"
    UNUSUAL_VOLATILITY = "unusual_volatility"
    EVENT_SIGNAL = "event_signal"
    FUNDAMENTAL_BREAKOUT = "fundamental_breakout"
    REGIME_CHANGE = "regime_change"
    CONVERGENCE = "convergence"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    INFO = "info"


class Alert(BaseModel):
    """Single alert produced by the alert engine."""
    alert_type: AlertType
    severity: AlertSeverity
    ticker: str = ""
    headline: str = ""
    description: str = ""
    source_engine: str = ""
    score: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actionable: bool = True
    metadata: dict = Field(default_factory=dict)


class AlertStream(BaseModel):
    """Collection of active alerts."""
    alerts: list[Alert] = Field(default_factory=list)
    total_critical: int = 0
    total_high: int = 0
    total_moderate: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
