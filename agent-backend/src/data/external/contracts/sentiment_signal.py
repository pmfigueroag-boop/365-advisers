"""
src/data/external/contracts/sentiment_signal.py
──────────────────────────────────────────────────────────────────────────────
Canonical contracts for social / community sentiment signals.

Distinct from NewsSentimentData (news-based). This captures community
platforms like Stocktwits, Reddit, Santiment.

Consumed by:
  - Alpha Signals (sentiment category)
  - Crowding Engine (social crowd signals)
  - Idea Generation (trending detection)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class SocialMention(BaseModel):
    """Single mention / message from a social platform."""
    platform: str = ""                     # "stocktwits", "reddit", "santiment"
    message: str = ""
    sentiment: str = "neutral"             # bullish, bearish, neutral
    timestamp: datetime | None = None
    likes: int = 0
    url: str | None = None


class SentimentSignal(BaseModel):
    """
    Aggregated social sentiment signal for a ticker.

    Provides community-derived bullish/bearish signals, trending scores,
    and conversation intensity metrics.
    """
    ticker: str
    platform: str = ""                     # primary source platform

    # Sentiment metrics
    bullish_pct: float | None = None       # 0–100
    bearish_pct: float | None = None       # 0–100
    sentiment_score: float | None = None   # −1.0 to +1.0 (normalized)

    # Volume metrics
    message_volume_24h: int = 0
    message_volume_7d: int = 0
    volume_change_pct: float | None = None # vs previous period

    # Trending
    trending_score: float | None = None    # 0–100
    watchlist_count: int | None = None
    is_trending: bool = False

    # Recent mentions (sample)
    recent_mentions: list[SocialMention] = Field(default_factory=list)

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> SentimentSignal:
        return cls(ticker=ticker, source="null")
