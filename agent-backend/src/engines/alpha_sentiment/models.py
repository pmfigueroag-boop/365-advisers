"""
src/engines/alpha_sentiment/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the Alpha Sentiment Engine.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class SentimentRegime(str, Enum):
    EUPHORIA = "euphoria"
    OPTIMISM = "optimism"
    NEUTRAL = "neutral"
    FEAR = "fear"
    PANIC = "panic"


class SentimentScoreResult(BaseModel):
    """Composite sentiment assessment for a ticker."""
    ticker: str
    composite_score: float = Field(0.0, ge=-100, le=100)  # -100 (extreme fear) to +100 (extreme greed)
    regime: SentimentRegime = SentimentRegime.NEUTRAL
    polarity: float | None = None          # -1 to +1
    mention_volume: int = 0
    volume_z_score: float | None = None    # vs 30d average
    momentum_of_attention: float | None = None  # rate of change
    news_intensity: float | None = None
    signals: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HypeAlert(BaseModel):
    """Detected hype spike for a ticker."""
    ticker: str
    volume_spike_pct: float = 0.0
    bullish_pct: float = 0.0
    z_score: float = 0.0
    severity: str = "moderate"  # moderate / high / extreme


class PanicSignal(BaseModel):
    """Detected panic signal."""
    ticker: str
    bearish_surge_pct: float = 0.0
    volume_spike_pct: float = 0.0
    severity: str = "moderate"


class SentimentDashboard(BaseModel):
    """Complete sentiment intelligence output."""
    scores: list[SentimentScoreResult] = Field(default_factory=list)
    hype_alerts: list[HypeAlert] = Field(default_factory=list)
    panic_signals: list[PanicSignal] = Field(default_factory=list)
    top_trending: list[str] = Field(default_factory=list)
    market_mood: SentimentRegime = SentimentRegime.NEUTRAL
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
