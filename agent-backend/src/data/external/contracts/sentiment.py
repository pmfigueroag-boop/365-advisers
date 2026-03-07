"""
src/data/external/contracts/sentiment.py
──────────────────────────────────────────────────────────────────────────────
Normalized contracts for news & sentiment intelligence.

Captures headlines, sentiment scores, catalyst detection, and narrative
shifts for the Idea Generation Engine, Decision Engine, and Alpha Signals.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    """Single news article with sentiment annotation."""
    title: str
    source: str
    published_at: datetime
    url: str | None = None
    sentiment_score: float = 0.0      # −1.0 to +1.0
    relevance: float = 0.0            # 0.0 to 1.0
    categories: list[str] = Field(default_factory=list)


class SentimentSummary(BaseModel):
    """Aggregated sentiment snapshot for a ticker."""
    ticker: str
    avg_sentiment_24h: float = 0.0
    avg_sentiment_7d: float = 0.0
    sentiment_momentum: float = 0.0    # 24h vs 7d delta
    article_count_24h: int = 0
    article_count_7d: int = 0
    dominant_narrative: str = ""
    catalyst_detected: bool = False
    catalyst_type: str | None = None   # earnings, FDA, M&A, regulatory...

    @classmethod
    def empty(cls, ticker: str = "") -> SentimentSummary:
        return cls(ticker=ticker)


class NewsSentimentData(BaseModel):
    """
    Complete news & sentiment output for a ticker.

    Consumed by:
      - Idea Generation (Event Detector)
      - Alpha Signals (sentiment category)
      - Decision Engine (CIO Memo context)
    """
    ticker: str
    summary: SentimentSummary | None = None
    recent_articles: list[NewsItem] = Field(default_factory=list)

    # GDELT enrichment (optional)
    geopolitical_tone: float | None = None       # GDELT avg tone for ticker-related events
    event_count_48h: int | None = None           # GDELT event count
    dominant_geopolitical_theme: str | None = None

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> NewsSentimentData:
        return cls(ticker=ticker, source="null")
