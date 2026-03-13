"""
src/engines/alpha_sentiment/engine.py
──────────────────────────────────────────────────────────────────────────────
Alpha Sentiment Engine — captures social and news sentiment signals.
Data Sources: Stocktwits, Santiment, GDELT, QuiverQuant (via EDPL)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_sentiment.models import (
    SentimentScoreResult, SentimentRegime, SentimentDashboard,
    HypeAlert, PanicSignal,
)
from src.engines._utils import safe_float as _f

logger = logging.getLogger("365advisers.alpha_sentiment.engine")


class AlphaSentimentEngine:
    """
    Produces sentiment scores, hype/panic alerts, and trending detection
    from social and news data.

    Usage::

        engine = AlphaSentimentEngine()
        result = engine.analyze("AAPL", sentiment_data)
        dashboard = engine.build_dashboard([result1, result2, ...])
    """

    def analyze(self, ticker: str, data: dict) -> SentimentScoreResult:
        """
        Analyze sentiment for a single ticker.

        Parameters
        ----------
        data : dict
            Keys: bullish_pct, bearish_pct, message_volume_24h,
                  message_volume_7d, trending_score, news_count,
                  avg_volume_30d (for z-score computation)
        """
        bull = _f(data.get("bullish_pct")) or 50.0
        bear = _f(data.get("bearish_pct")) or 50.0
        vol_24h = int(data.get("message_volume_24h", 0))
        vol_7d = int(data.get("message_volume_7d", 0))
        avg_vol = _f(data.get("avg_volume_30d")) or max(vol_7d / 7.0, 1)
        news_count = int(data.get("news_count", 0))
        trending = _f(data.get("trending_score"))

        # Polarity: -1 to +1
        polarity = (bull - bear) / 100.0

        # Volume z-score — use Poisson-like proxy: σ ≈ √μ for count data
        sigma = max(avg_vol ** 0.5, 1.0) if avg_vol > 0 else 1.0
        vol_z = (vol_24h - avg_vol) / sigma if sigma > 0 else 0

        # Momentum of attention: 24h vs 7d daily avg
        daily_avg_7d = vol_7d / 7.0 if vol_7d > 0 else 0
        momentum = (vol_24h / max(daily_avg_7d, 1) - 1.0) if daily_avg_7d > 0 else 0

        # News intensity: normalized 0–1
        news_intensity = min(news_count / 20.0, 1.0) if news_count > 0 else 0

        # Composite: -100 to +100
        composite = (
            0.40 * polarity * 100
            + 0.30 * min(max(momentum * 25, -50), 50)
            + 0.30 * news_intensity * (50 if polarity >= 0 else -50)
        )
        composite = round(min(max(composite, -100), 100), 1)

        regime = self._classify_regime(composite)
        signals = self._generate_signals(ticker, polarity, vol_z, momentum, regime)

        return SentimentScoreResult(
            ticker=ticker,
            composite_score=composite,
            regime=regime,
            polarity=round(polarity, 3),
            mention_volume=vol_24h,
            volume_z_score=round(vol_z, 2),
            momentum_of_attention=round(momentum, 2),
            news_intensity=round(news_intensity, 2),
            signals=signals,
        )

    def detect_hype(self, ticker: str, data: dict) -> HypeAlert | None:
        """Detect hype spike: high bullish + volume surge."""
        bull = _f(data.get("bullish_pct")) or 0
        vol_24h = int(data.get("message_volume_24h", 0))
        avg_vol = _f(data.get("avg_volume_30d")) or 1
        vol_spike = ((vol_24h / avg_vol) - 1) * 100 if avg_vol > 0 else 0
        z = vol_24h / max(avg_vol, 1)

        if bull > 70 and vol_spike > 100:
            severity = "extreme" if vol_spike > 300 else "high" if vol_spike > 200 else "moderate"
            return HypeAlert(ticker=ticker, volume_spike_pct=round(vol_spike, 1), bullish_pct=bull, z_score=round(z, 2), severity=severity)
        return None

    def detect_panic(self, ticker: str, data: dict) -> PanicSignal | None:
        """Detect panic: high bearish + volume surge."""
        bear = _f(data.get("bearish_pct")) or 0
        vol_24h = int(data.get("message_volume_24h", 0))
        avg_vol = _f(data.get("avg_volume_30d")) or 1
        vol_spike = ((vol_24h / avg_vol) - 1) * 100 if avg_vol > 0 else 0

        if bear > 65 and vol_spike > 80:
            severity = "extreme" if bear > 85 else "high" if bear > 75 else "moderate"
            return PanicSignal(ticker=ticker, bearish_surge_pct=bear, volume_spike_pct=round(vol_spike, 1), severity=severity)
        return None

    def build_dashboard(self, scores: list[SentimentScoreResult], hypes: list[HypeAlert] | None = None, panics: list[PanicSignal] | None = None) -> SentimentDashboard:
        avg_score = sum(s.composite_score for s in scores) / max(len(scores), 1)
        market_mood = self._classify_regime(avg_score)
        trending = [s.ticker for s in sorted(scores, key=lambda s: s.mention_volume, reverse=True)[:10]]
        return SentimentDashboard(
            scores=scores, hype_alerts=hypes or [], panic_signals=panics or [],
            top_trending=trending, market_mood=market_mood,
        )

    def _classify_regime(self, score: float) -> SentimentRegime:
        if score >= 60: return SentimentRegime.EUPHORIA
        if score >= 20: return SentimentRegime.OPTIMISM
        if score >= -20: return SentimentRegime.NEUTRAL
        if score >= -60: return SentimentRegime.FEAR
        return SentimentRegime.PANIC

    def _generate_signals(self, ticker: str, polarity: float, vol_z: float, momentum: float, regime: SentimentRegime) -> list[str]:
        signals = [f"Sentiment regime: {regime.value}"]
        if polarity > 0.5: signals.append(f"Strong bullish polarity: {polarity:.2f}")
        elif polarity < -0.5: signals.append(f"Strong bearish polarity: {polarity:.2f}")
        if vol_z > 2.0: signals.append(f"Volume spike (z={vol_z:.1f})")
        if momentum > 1.0: signals.append("Attention momentum accelerating")
        elif momentum < -0.5: signals.append("Attention fading")
        return signals
