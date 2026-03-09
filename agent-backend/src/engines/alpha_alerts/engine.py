"""
src/engines/alpha_alerts/engine.py
──────────────────────────────────────────────────────────────────────────────
Alpha Alert Engine — monitors outputs from all alpha engines and
generates alerts when configurable thresholds are breached.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_alerts.models import (
    Alert, AlertType, AlertSeverity, AlertStream,
)
from src.engines.alpha_fundamental.models import FundamentalScore
from src.engines.alpha_macro.models import MacroScore, MacroRegime
from src.engines.alpha_sentiment.models import SentimentScoreResult, SentimentRegime
from src.engines.alpha_volatility.models import VolScore, VolRegime
from src.engines.alpha_event.models import EventScore

logger = logging.getLogger("365advisers.alpha_alerts.engine")


class AlertEngine:
    """
    Generates alerts from alpha engine outputs.

    Usage::

        engine = AlertEngine()
        stream = engine.evaluate(
            fundamentals=[...], macro_score=..., sentiments=[...],
            vol_score=..., events=[...],
        )
    """

    def evaluate(
        self,
        fundamentals: list[FundamentalScore] | None = None,
        macro_score: MacroScore | None = None,
        sentiments: list[SentimentScoreResult] | None = None,
        vol_score: VolScore | None = None,
        events: list[EventScore] | None = None,
    ) -> AlertStream:
        alerts: list[Alert] = []

        if macro_score:
            alerts.extend(self._check_macro(macro_score))
        if sentiments:
            for s in sentiments:
                alerts.extend(self._check_sentiment(s))
        if vol_score:
            alerts.extend(self._check_volatility(vol_score))
        if events:
            for e in events:
                alerts.extend(self._check_events(e))
        if fundamentals:
            for f in fundamentals:
                alerts.extend(self._check_fundamental(f))

        # Sort by severity then score
        sev_order = {AlertSeverity.CRITICAL: 0, AlertSeverity.HIGH: 1, AlertSeverity.MODERATE: 2, AlertSeverity.INFO: 3}
        alerts.sort(key=lambda a: (sev_order.get(a.severity, 9), -abs(a.score)))

        return AlertStream(
            alerts=alerts,
            total_critical=sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL),
            total_high=sum(1 for a in alerts if a.severity == AlertSeverity.HIGH),
            total_moderate=sum(1 for a in alerts if a.severity == AlertSeverity.MODERATE),
        )

    def _check_macro(self, ms: MacroScore) -> list[Alert]:
        alerts = []
        if ms.regime == MacroRegime.RECESSION:
            alerts.append(Alert(
                alert_type=AlertType.REGIME_CHANGE, severity=AlertSeverity.CRITICAL,
                headline="Macro Regime: RECESSION", description=f"Regime confidence: {ms.regime_confidence:.0%}",
                source_engine="alpha_macro", score=ms.composite_score,
            ))
        elif ms.regime == MacroRegime.SLOWDOWN and ms.regime_confidence > 0.5:
            alerts.append(Alert(
                alert_type=AlertType.MACRO_SHIFT, severity=AlertSeverity.HIGH,
                headline="Macro Regime: SLOWDOWN", description="Economic momentum decelerating",
                source_engine="alpha_macro", score=ms.composite_score,
            ))
        return alerts

    def _check_sentiment(self, s: SentimentScoreResult) -> list[Alert]:
        alerts = []
        if s.regime == SentimentRegime.PANIC:
            alerts.append(Alert(
                alert_type=AlertType.SENTIMENT_PANIC, severity=AlertSeverity.HIGH,
                ticker=s.ticker, headline=f"Panic sentiment on {s.ticker}",
                description=f"Score: {s.composite_score:.0f}, polarity: {s.polarity}",
                source_engine="alpha_sentiment", score=abs(s.composite_score),
            ))
        if s.regime == SentimentRegime.EUPHORIA:
            alerts.append(Alert(
                alert_type=AlertType.SENTIMENT_SPIKE, severity=AlertSeverity.MODERATE,
                ticker=s.ticker, headline=f"Euphoria spike on {s.ticker}",
                description=f"Score: {s.composite_score:.0f}",
                source_engine="alpha_sentiment", score=s.composite_score,
            ))
        if s.volume_z_score and s.volume_z_score > 3.0:
            alerts.append(Alert(
                alert_type=AlertType.SENTIMENT_SPIKE, severity=AlertSeverity.HIGH,
                ticker=s.ticker, headline=f"Volume anomaly on {s.ticker}",
                description=f"Mention volume z-score: {s.volume_z_score:.1f}",
                source_engine="alpha_sentiment", score=s.volume_z_score * 10,
            ))
        return alerts

    def _check_volatility(self, vs: VolScore) -> list[Alert]:
        alerts = []
        if vs.regime == VolRegime.EXTREME:
            alerts.append(Alert(
                alert_type=AlertType.UNUSUAL_VOLATILITY, severity=AlertSeverity.CRITICAL,
                headline=f"VIX EXTREME: {vs.vix_level}",
                description="Market in extreme volatility regime",
                source_engine="alpha_volatility", score=vs.composite_risk,
            ))
        elif vs.regime == VolRegime.ELEVATED:
            alerts.append(Alert(
                alert_type=AlertType.UNUSUAL_VOLATILITY, severity=AlertSeverity.HIGH,
                headline=f"VIX Elevated: {vs.vix_level}",
                source_engine="alpha_volatility", score=vs.composite_risk,
            ))
        if vs.iv_rank and vs.iv_rank > 90:
            alerts.append(Alert(
                alert_type=AlertType.UNUSUAL_VOLATILITY, severity=AlertSeverity.HIGH,
                headline=f"IV Rank at {vs.iv_rank:.0f}th percentile",
                source_engine="alpha_volatility", score=vs.iv_rank,
            ))
        return alerts

    def _check_events(self, es: EventScore) -> list[Alert]:
        alerts = []
        if abs(es.composite_score) > 50 and es.most_significant:
            sev = AlertSeverity.CRITICAL if abs(es.composite_score) > 75 else AlertSeverity.HIGH
            alerts.append(Alert(
                alert_type=AlertType.EVENT_SIGNAL, severity=sev,
                ticker=es.ticker,
                headline=f"Major event: {es.most_significant.headline}",
                description=f"Impact: {es.composite_score:+.0f}",
                source_engine="alpha_event", score=abs(es.composite_score),
            ))
        return alerts

    def _check_fundamental(self, fs: FundamentalScore) -> list[Alert]:
        alerts = []
        if fs.composite_score >= 85:
            alerts.append(Alert(
                alert_type=AlertType.FUNDAMENTAL_BREAKOUT, severity=AlertSeverity.MODERATE,
                ticker=fs.ticker,
                headline=f"Fundamental breakout: {fs.ticker} ({fs.grade.value})",
                description=f"Score: {fs.composite_score:.0f}/100",
                source_engine="alpha_fundamental", score=fs.composite_score,
            ))
        return alerts
