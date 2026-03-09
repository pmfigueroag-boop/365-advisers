"""
src/engines/investment_brain/opportunity_detector.py
──────────────────────────────────────────────────────────────────────────────
Opportunity Detector — identifies actionable investment opportunities by
cross-referencing alpha scores, sentiment shifts, volatility anomalies,
event signals, and the current market regime.

Consumes: SuperAlphaEngine rankings, sentiment scores, volatility data,
          event scores, regime classification.
Output:   Prioritised list of DetectedOpportunity.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.investment_brain.models import (
    DetectedOpportunity,
    MarketRegime,
    OpportunityType,
    RegimeClassification,
)

logger = logging.getLogger("365advisers.investment_brain.opportunity")

# ── Regime-aligned sectors ───────────────────────────────────────────────────

_REGIME_SECTORS: dict[MarketRegime, list[str]] = {
    MarketRegime.EXPANSION: ["Technology", "Consumer Discretionary", "Industrials", "Financials"],
    MarketRegime.SLOWDOWN: ["Healthcare", "Utilities", "Consumer Staples"],
    MarketRegime.RECESSION: ["Utilities", "Healthcare", "Consumer Staples"],
    MarketRegime.RECOVERY: ["Financials", "Real Estate", "Industrials", "Materials"],
    MarketRegime.HIGH_VOLATILITY: ["Utilities", "Healthcare", "Gold", "Cash"],
    MarketRegime.LIQUIDITY_EXPANSION: ["Technology", "Growth", "Real Estate", "Crypto"],
}


class OpportunityDetector:
    """
    Identifies investment opportunities from engine signals.

    Usage::

        detector = OpportunityDetector()
        opportunities = detector.detect(
            alpha_profiles=profiles,
            sentiment_scores=scores,
            vol_data=vol,
            event_scores=events,
            regime=regime_classification,
        )
    """

    def detect(
        self,
        alpha_profiles: list[dict] | None = None,
        sentiment_scores: list[dict] | None = None,
        vol_data: dict | None = None,
        event_scores: list[dict] | None = None,
        regime: RegimeClassification | None = None,
    ) -> list[DetectedOpportunity]:
        """
        Detect investment opportunities from cross-engine signals.

        Parameters
        ----------
        alpha_profiles : list[dict] | None
            List of SuperAlpha profiles: {ticker, composite_alpha_score,
            tier, top_drivers, factor_scores: {value, momentum, ...}, sector}
        sentiment_scores : list[dict] | None
            List of {ticker, composite_score, regime, polarity, momentum_of_attention}
        vol_data : dict | None
            Global volatility data: {vix_current, iv_rank, regime}
        event_scores : list[dict] | None
            List of {ticker, composite_score, bullish_events, bearish_events,
            most_significant_headline, signals}
        regime : RegimeClassification | None
            Current market regime classification
        """
        profiles = alpha_profiles or []
        sentiments = sentiment_scores or []
        vol = vol_data or {}
        events = event_scores or []
        current_regime = regime.regime if regime else MarketRegime.EXPANSION

        opportunities: list[DetectedOpportunity] = []

        # Build look-up maps
        sentiment_map = {s.get("ticker", ""): s for s in sentiments}
        event_map = {e.get("ticker", ""): e for e in events}
        favored_sectors = _REGIME_SECTORS.get(current_regime, [])

        for profile in profiles:
            ticker = profile.get("ticker", "")
            if not ticker:
                continue
            cas = _f(profile.get("composite_alpha_score")) or 0
            tier = profile.get("tier", "")
            sector = profile.get("sector", "")
            factors = profile.get("factor_scores", {})
            sent = sentiment_map.get(ticker, {})
            evt = event_map.get(ticker, {})

            # ── 1. Undervalued assets ────────────────────────────────────
            value_score = _f(factors.get("value")) or 0
            if value_score > 60 and cas > 50:
                confidence = min((value_score / 100) * 0.6 + (cas / 100) * 0.4, 1.0)
                signals = [f"Value factor score: {value_score:.0f}", f"Composite Alpha: {cas:.0f}"]
                if sector in favored_sectors:
                    signals.append(f"Sector {sector} aligned with {current_regime.value} regime")
                    confidence = min(confidence + 0.1, 1.0)
                opportunities.append(DetectedOpportunity(
                    ticker=ticker,
                    opportunity_type=OpportunityType.UNDERVALUED,
                    alpha_score=round(cas, 1),
                    confidence=round(confidence, 3),
                    signals=signals,
                    justification=f"{ticker} shows deep value characteristics with alpha score {cas:.0f} and value factor {value_score:.0f}.",
                    regime_alignment=f"{'Aligned' if sector in favored_sectors else 'Neutral'} with {current_regime.value} regime",
                ))

            # ── 2. Momentum breakouts ────────────────────────────────────
            momentum_score = _f(factors.get("momentum")) or 0
            if momentum_score > 65 and cas > 55:
                confidence = min((momentum_score / 100) * 0.5 + (cas / 100) * 0.5, 1.0)
                signals = [f"Momentum factor: {momentum_score:.0f}", f"Composite Alpha: {cas:.0f}"]
                opportunities.append(DetectedOpportunity(
                    ticker=ticker,
                    opportunity_type=OpportunityType.MOMENTUM_BREAKOUT,
                    alpha_score=round(cas, 1),
                    confidence=round(confidence, 3),
                    signals=signals,
                    justification=f"{ticker} exhibiting momentum breakout with strong trend confirmation (momentum={momentum_score:.0f}).",
                ))

            # ── 3. Sentiment-driven moves ────────────────────────────────
            sent_score = _f(sent.get("composite_score")) or 0
            polarity = _f(sent.get("polarity")) or 0
            attn_momentum = _f(sent.get("momentum_of_attention")) or 0
            if abs(sent_score) > 40 and abs(polarity) > 0.3 and attn_momentum > 0.5:
                direction = "bullish" if sent_score > 0 else "bearish"
                confidence = min(abs(sent_score) / 100 * 0.6 + abs(polarity) * 0.4, 1.0)
                signals = [
                    f"Sentiment score: {sent_score:.0f} ({direction})",
                    f"Polarity: {polarity:.2f}",
                    f"Attention momentum: {attn_momentum:.2f}",
                ]
                opportunities.append(DetectedOpportunity(
                    ticker=ticker,
                    opportunity_type=OpportunityType.SENTIMENT_DRIVEN,
                    alpha_score=round(cas, 1),
                    confidence=round(confidence, 3),
                    signals=signals,
                    justification=f"{ticker} experiencing significant {direction} sentiment shift with accelerating attention.",
                ))

            # ── 4. Event catalysts ───────────────────────────────────────
            evt_score = _f(evt.get("composite_score")) or 0
            evt_bullish = int(evt.get("bullish_events", 0))
            if abs(evt_score) > 30 and evt_bullish > 0:
                confidence = min(abs(evt_score) / 100 * 0.7 + 0.1 * evt_bullish, 1.0)
                signals = [f"Event score: {evt_score:.0f}", f"Bullish events: {evt_bullish}"]
                headline = evt.get("most_significant_headline", "")
                if headline:
                    signals.append(f"Top event: {headline}")
                opportunities.append(DetectedOpportunity(
                    ticker=ticker,
                    opportunity_type=OpportunityType.EVENT_CATALYST,
                    alpha_score=round(cas, 1),
                    confidence=round(confidence, 3),
                    signals=signals,
                    justification=f"{ticker} has {evt_bullish} bullish corporate events creating a catalyst-driven opportunity.",
                ))

            # ── 5. Macro-aligned opportunities ───────────────────────────
            if sector in favored_sectors and cas > 50 and tier in ("alpha", "strong_alpha", "elite"):
                macro_score = _f(factors.get("macro")) or 0
                confidence = min(cas / 100 * 0.5 + (1.0 if sector in favored_sectors else 0.3) * 0.5, 1.0)
                signals = [
                    f"Sector {sector} favored in {current_regime.value} regime",
                    f"Alpha tier: {tier}",
                    f"Macro factor: {macro_score:.0f}",
                ]
                opportunities.append(DetectedOpportunity(
                    ticker=ticker,
                    opportunity_type=OpportunityType.MACRO_ALIGNED,
                    alpha_score=round(cas, 1),
                    confidence=round(confidence, 3),
                    signals=signals,
                    justification=f"{ticker} in {sector} sector is well-positioned for the current {current_regime.value} regime.",
                    regime_alignment=f"Strong alignment with {current_regime.value}",
                ))

        # De-duplicate: keep the highest-scored occurrence per ticker
        seen: dict[str, DetectedOpportunity] = {}
        for opp in opportunities:
            key = f"{opp.ticker}_{opp.opportunity_type.value}"
            if key not in seen or opp.alpha_score > seen[key].alpha_score:
                seen[key] = opp

        result = sorted(seen.values(), key=lambda o: o.alpha_score, reverse=True)
        return result[:20]


def _f(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
