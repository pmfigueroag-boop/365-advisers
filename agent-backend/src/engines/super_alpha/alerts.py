"""
src/engines/super_alpha/alerts.py
──────────────────────────────────────────────────────────────────────────────
Alert rule engine for the Super Alpha system.

Generates alerts when:
  - Asset enters top 10th percentile by CAS
  - Sentiment score changes > 30 pts
  - High-severity corporate events detected
  - Macro regime transitions
  - Factor convergence detected (≥6 factors bullish)
  - Volatility spike
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.super_alpha.models import (
    AlertType,
    AlphaTier,
    CompositeAlphaProfile,
    FactorName,
    SuperAlphaAlert,
)

logger = logging.getLogger("365advisers.super_alpha.alerts")


class SuperAlphaAlertEngine:
    """
    Evaluates current asset profiles and generates actionable alerts.

    Usage::

        alert_engine = SuperAlphaAlertEngine()
        alerts = alert_engine.evaluate(profiles, previous_profiles)
    """

    def __init__(
        self,
        top_percentile_threshold: float = 90.0,
        sentiment_shift_threshold: float = 30.0,
        event_severity_threshold: float = 60.0,
    ) -> None:
        self._top_pct = top_percentile_threshold
        self._sent_shift = sentiment_shift_threshold
        self._event_threshold = event_severity_threshold

    def evaluate(
        self,
        profiles: list[CompositeAlphaProfile],
        previous_profiles: list[CompositeAlphaProfile] | None = None,
    ) -> list[SuperAlphaAlert]:
        """
        Generate alerts from current (and optionally previous) profiles.

        Parameters
        ----------
        profiles : list[CompositeAlphaProfile]
            Current universe profiles, already ranked.
        previous_profiles : list[CompositeAlphaProfile] | None
            Previous snapshot for change detection.
        """
        alerts: list[SuperAlphaAlert] = []
        prev_map = {p.ticker: p for p in (previous_profiles or [])}

        for p in profiles:
            # ── Top percentile alert ──────────────────────────────────────
            if p.percentile is not None and p.percentile >= self._top_pct:
                alerts.append(SuperAlphaAlert(
                    alert_type=AlertType.TOP_PERCENTILE,
                    ticker=p.ticker,
                    severity="high",
                    headline=f"{p.ticker} entered top {100 - self._top_pct:.0f}th percentile",
                    detail=(
                        f"Composite Alpha Score: {p.composite_alpha_score:.1f} "
                        f"({p.tier.value}). "
                        f"Top drivers: {', '.join(p.top_drivers[:3])}"
                    ),
                    factor_scores=self._factor_dict(p),
                ))

            # ── Factor convergence ────────────────────────────────────────
            if p.factor_agreement >= 6:
                alerts.append(SuperAlphaAlert(
                    alert_type=AlertType.FACTOR_CONVERGENCE,
                    ticker=p.ticker,
                    severity="high",
                    headline=f"{p.ticker}: {p.factor_agreement}/8 factors bullish",
                    detail=(
                        f"Multi-factor convergence detected. "
                        f"CAS={p.composite_alpha_score:.1f}, "
                        f"Tier={p.tier.value}"
                    ),
                    factor_scores=self._factor_dict(p),
                ))

            # ── Sentiment shift ───────────────────────────────────────────
            prev = prev_map.get(p.ticker)
            if prev:
                sent_delta = abs(p.sentiment.score - prev.sentiment.score)
                if sent_delta >= self._sent_shift:
                    direction = "improvement" if p.sentiment.score > prev.sentiment.score else "deterioration"
                    alerts.append(SuperAlphaAlert(
                        alert_type=AlertType.SENTIMENT_SHIFT,
                        ticker=p.ticker,
                        severity="high" if sent_delta > 50 else "moderate",
                        headline=f"{p.ticker} sentiment {direction}: Δ{sent_delta:.0f} pts",
                        detail=(
                            f"Sentiment moved from {prev.sentiment.score:.0f} → "
                            f"{p.sentiment.score:.0f}"
                        ),
                        factor_scores={"sentiment": p.sentiment.score},
                    ))

            # ── Event-driven ──────────────────────────────────────────────
            if p.event.score > self._event_threshold:
                alerts.append(SuperAlphaAlert(
                    alert_type=AlertType.CORPORATE_EVENT,
                    ticker=p.ticker,
                    severity="high",
                    headline=f"{p.ticker}: high-impact corporate event detected",
                    detail=f"Event score: {p.event.score:.1f}. " + (
                        "; ".join(p.event.signals[:2]) if p.event.signals else ""
                    ),
                    factor_scores={"event": p.event.score},
                ))

            # ── Volatility spike ──────────────────────────────────────────
            if p.volatility.score < 25:
                alerts.append(SuperAlphaAlert(
                    alert_type=AlertType.VOLATILITY_SPIKE,
                    ticker=p.ticker,
                    severity="high" if p.volatility.score < 15 else "moderate",
                    headline=f"{p.ticker}: elevated volatility risk",
                    detail=(
                        f"Volatility stability score: {p.volatility.score:.0f}/100 "
                        f"(lower = more risk). " +
                        ("; ".join(p.volatility.signals[:2]) if p.volatility.signals else "")
                    ),
                    factor_scores={"volatility": p.volatility.score},
                ))

        # ── Market-level: macro regime ────────────────────────────────────
        if profiles:
            avg_macro = sum(p.macro.score for p in profiles) / len(profiles)
            if avg_macro < 30:
                alerts.append(SuperAlphaAlert(
                    alert_type=AlertType.MACRO_REGIME_CHANGE,
                    severity="critical",
                    headline="Macro regime: contraction signal",
                    detail=(
                        f"Average macro factor score: {avg_macro:.1f}/100. "
                        f"Consider defensive positioning."
                    ),
                ))
            elif avg_macro > 70:
                alerts.append(SuperAlphaAlert(
                    alert_type=AlertType.MACRO_REGIME_CHANGE,
                    severity="moderate",
                    headline="Macro regime: expansion signal",
                    detail=(
                        f"Average macro factor score: {avg_macro:.1f}/100. "
                        f"Pro-growth environment."
                    ),
                ))

        # Sort by severity
        sev_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        alerts.sort(key=lambda a: sev_order.get(a.severity, 4))

        return alerts

    @staticmethod
    def _factor_dict(profile: CompositeAlphaProfile) -> dict[str, float]:
        return {
            "value": profile.value.score,
            "momentum": profile.momentum.score,
            "quality": profile.quality.score,
            "size": profile.size.score,
            "volatility": profile.volatility.score,
            "sentiment": profile.sentiment.score,
            "macro": profile.macro.score,
            "event": profile.event.score,
        }
