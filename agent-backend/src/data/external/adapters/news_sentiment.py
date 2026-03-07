"""
src/data/external/adapters/news_sentiment.py
──────────────────────────────────────────────────────────────────────────────
News & Sentiment Intelligence Adapter.

Provides news headlines, sentiment scores, and catalyst detection.

Data sources (in priority order):
  1. Polygon.io news API (if POLYGON_API_KEY is set)
  2. Custom NEWS_API_KEY endpoint (if set)
  3. yfinance news data (always available, limited sentiment)

The adapter feeds:
  - Idea Generation Engine (Event Detector)
  - Alpha Signals (sentiment category)
  - Decision Engine / CIO Memo (context)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from src.config import get_settings
from src.data.external.base import (
    DataDomain,
    HealthStatus,
    ProviderAdapter,
    ProviderCapability,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
)
from src.data.external.contracts.sentiment import (
    NewsItem,
    NewsSentimentData,
    SentimentSummary,
)

logger = logging.getLogger("365advisers.external.sentiment")

# Simple keyword-based sentiment (fallback when no NLP API is available)
_POSITIVE_KEYWORDS = {
    "upgrade", "beat", "outperform", "growth", "record", "surge",
    "acquisition", "bullish", "strong", "breakout", "rally", "profit",
    "approval", "launch", "partnership", "exceed", "dividend", "buy",
}
_NEGATIVE_KEYWORDS = {
    "downgrade", "miss", "underperform", "decline", "loss", "layoff",
    "bearish", "weak", "crash", "recall", "lawsuit", "investigation",
    "sell", "warning", "cut", "bankruptcy", "default", "delay",
}
_CATALYST_KEYWORDS = {
    "earnings": "earnings",
    "FDA": "fda",
    "acquisition": "m_and_a",
    "merger": "m_and_a",
    "takeover": "m_and_a",
    "regulatory": "regulatory",
    "guidance": "guidance",
    "split": "corporate_action",
    "buyback": "corporate_action",
    "dividend": "corporate_action",
}


class NewsSentimentAdapter(ProviderAdapter):
    """
    News & sentiment adapter with multi-source fallback.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._polygon_key = settings.POLYGON_API_KEY
        self._news_key = settings.NEWS_API_KEY
        self._timeout = settings.EDPL_NEWS_TIMEOUT
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "news_sentiment"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.SENTIMENT

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.NEWS_HEADLINES,
            ProviderCapability.SENTIMENT_SCORES,
            ProviderCapability.CATALYST_DETECTION,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch news & sentiment for a ticker."""
        ticker = (request.ticker or "").upper()
        if not ticker:
            return self._error_response("ticker is required")

        t0 = time.perf_counter()

        try:
            articles: list[NewsItem] = []

            # Try Polygon news first
            if self._polygon_key:
                articles = await self._fetch_polygon_news(ticker)

            # Fallback to yfinance news
            if not articles:
                articles = await self._fetch_yfinance_news(ticker)

            # Build sentiment summary from articles
            summary = self._build_summary(ticker, articles)

            data = NewsSentimentData(
                ticker=ticker,
                summary=summary,
                recent_articles=articles[:20],  # Cap at 20
                source="polygon_news" if self._polygon_key and articles else "yfinance_news",
                fetched_at=datetime.now(timezone.utc),
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Sentiment fetch error for {ticker}: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            provider_name=self.name,
            domain=self.domain,
            status=ProviderStatus.ACTIVE,
            message="yfinance fallback always available",
        )

    # ── Internal ──────────────────────────────────────────────────────────

    async def _fetch_polygon_news(self, ticker: str) -> list[NewsItem]:
        """Fetch news from Polygon.io reference news API."""
        try:
            resp = await self._client.get(
                "https://api.polygon.io/v2/reference/news",
                params={
                    "ticker": ticker,
                    "limit": 20,
                    "sort": "published_utc",
                    "order": "desc",
                    "apiKey": self._polygon_key,
                },
            )
            if resp.status_code != 200:
                return []

            data = resp.json().get("results", [])
            articles: list[NewsItem] = []

            for item in data:
                published = item.get("published_utc", "")
                try:
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pub_dt = datetime.now(timezone.utc)

                title = item.get("title", "")
                sentiment = self._score_text(title)

                articles.append(NewsItem(
                    title=title,
                    source=item.get("publisher", {}).get("name", "unknown"),
                    published_at=pub_dt,
                    url=item.get("article_url"),
                    sentiment_score=sentiment,
                    relevance=0.8,  # Polygon relevance is generally high
                    categories=item.get("keywords", [])[:5],
                ))

            return articles

        except Exception as exc:
            logger.debug(f"Polygon news fetch failed for {ticker}: {exc}")
            return []

    async def _fetch_yfinance_news(self, ticker: str) -> list[NewsItem]:
        """Fetch news from yfinance as fallback."""
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            news = getattr(stock, "news", None) or []

            articles: list[NewsItem] = []
            for item in news[:20]:
                title = item.get("title", "")
                pub_ts = item.get("providerPublishTime", 0)
                try:
                    pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
                except (ValueError, OSError):
                    pub_dt = datetime.now(timezone.utc)

                sentiment = self._score_text(title)

                articles.append(NewsItem(
                    title=title,
                    source=item.get("publisher", "unknown"),
                    published_at=pub_dt,
                    url=item.get("link"),
                    sentiment_score=sentiment,
                    relevance=0.6,  # yfinance news is less curated
                    categories=[],
                ))

            return articles

        except Exception as exc:
            logger.debug(f"yfinance news fetch failed for {ticker}: {exc}")
            return []

    def _score_text(self, text: str) -> float:
        """Simple keyword-based sentiment scoring (-1.0 to +1.0)."""
        if not text:
            return 0.0

        words = set(text.lower().split())
        pos = len(words & _POSITIVE_KEYWORDS)
        neg = len(words & _NEGATIVE_KEYWORDS)
        total = pos + neg

        if total == 0:
            return 0.0

        return round((pos - neg) / total, 3)

    def _build_summary(
        self, ticker: str, articles: list[NewsItem],
    ) -> SentimentSummary:
        """Build an aggregated sentiment summary from articles."""
        if not articles:
            return SentimentSummary.empty(ticker)

        now = datetime.now(timezone.utc)

        # Split into 24h and 7d buckets
        sentiments_24h = [a.sentiment_score for a in articles
                          if (now - a.published_at).total_seconds() < 86400]
        sentiments_7d = [a.sentiment_score for a in articles
                         if (now - a.published_at).total_seconds() < 604800]

        avg_24h = sum(sentiments_24h) / len(sentiments_24h) if sentiments_24h else 0.0
        avg_7d = sum(sentiments_7d) / len(sentiments_7d) if sentiments_7d else 0.0

        # Catalyst detection
        catalyst_detected = False
        catalyst_type: str | None = None
        all_text = " ".join(a.title for a in articles[:10]).lower()
        for keyword, cat_type in _CATALYST_KEYWORDS.items():
            if keyword.lower() in all_text:
                catalyst_detected = True
                catalyst_type = cat_type
                break

        return SentimentSummary(
            ticker=ticker,
            avg_sentiment_24h=round(avg_24h, 3),
            avg_sentiment_7d=round(avg_7d, 3),
            sentiment_momentum=round(avg_24h - avg_7d, 3),
            article_count_24h=len(sentiments_24h),
            article_count_7d=len(sentiments_7d),
            catalyst_detected=catalyst_detected,
            catalyst_type=catalyst_type,
        )
