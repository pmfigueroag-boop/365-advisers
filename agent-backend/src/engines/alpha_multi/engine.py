"""
src/engines/alpha_multi/engine.py
──────────────────────────────────────────────────────────────────────────────
Multi-Strategy Alpha Engine — combines signals from all 5 Alpha engines
into a unified ranking, heatmap, and conviction model.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_multi.models import (
    AlphaConviction, AssetAlphaProfile, HeatmapCell, MultiAlphaResult,
)

logger = logging.getLogger("365advisers.alpha_multi.engine")

# Default engine weights — regime-adaptive in production
_DEFAULT_WEIGHTS = {
    "fundamental": 0.30,
    "macro": 0.15,
    "sentiment": 0.20,
    "volatility": 0.15,
    "event": 0.20,
}

_CONVERGENCE_BONUS = 5.0  # Added when 4+ engines agree


class MultiStrategyAlphaEngine:
    """
    Combines sub-engine scores into a composite alpha ranking.

    Usage::

        engine = MultiStrategyAlphaEngine()
        result = engine.rank(ticker_scores)
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or _DEFAULT_WEIGHTS.copy()

    def rank(self, ticker_scores: list[dict]) -> MultiAlphaResult:
        """
        Produce composite rankings from per-ticker sub-engine scores.

        Parameters
        ----------
        ticker_scores : list[dict]
            Each dict has keys: ticker, fundamental (0–100), macro (0–100),
            sentiment (-100 to +100), volatility_risk (0–100), event (-100 to +100),
            signals (list[str])
        """
        profiles = []
        heatmap = []

        for ts in ticker_scores:
            ticker = ts["ticker"]
            fund = _clamp(ts.get("fundamental", 50))
            macro = _clamp(ts.get("macro", 50))
            sent_raw = ts.get("sentiment", 0)
            sent = _clamp((sent_raw + 100) / 2)  # rescale -100..100 → 0..100
            vol_raw = ts.get("volatility_risk", 50)
            vol = _clamp(100 - vol_raw)  # invert: low risk = high score
            evt_raw = ts.get("event", 0)
            evt = _clamp((evt_raw + 100) / 2)

            # Weighted composite
            w = self._weights
            composite = (
                w["fundamental"] * fund
                + w["macro"] * macro
                + w["sentiment"] * sent
                + w["volatility"] * vol
                + w["event"] * evt
            )

            # Convergence detection
            threshold = 60
            bullish = sum(1 for s in [fund, macro, sent, vol, evt] if s >= threshold)
            bearish = sum(1 for s in [fund, macro, sent, vol, evt] if s < 40)
            bonus = _CONVERGENCE_BONUS if bullish >= 4 else 0
            composite = min(composite + bonus, 100)

            conviction = self._classify_conviction(composite, bullish, bearish)
            signals = ts.get("signals", [])[:5]

            profiles.append(AssetAlphaProfile(
                ticker=ticker, composite_alpha=round(composite, 1),
                conviction=conviction,
                fundamental_score=round(fund, 1), macro_score=round(macro, 1),
                sentiment_score=round(sent, 1), volatility_risk=round(vol_raw, 1),
                event_score=round(evt, 1),
                engines_bullish=bullish, engines_bearish=bearish,
                convergence_bonus=bonus, top_signals=signals,
            ))

            heatmap.append(HeatmapCell(
                ticker=ticker, fundamental=round(fund, 1),
                macro=round(macro, 1), sentiment=round(sent, 1),
                volatility=round(vol, 1), event=round(evt, 1),
                composite=round(composite, 1),
            ))

        # Sort by composite
        profiles.sort(key=lambda p: p.composite_alpha, reverse=True)
        heatmap.sort(key=lambda h: h.composite, reverse=True)

        top_opps = [p.ticker for p in profiles if p.conviction in (AlphaConviction.STRONG_BUY, AlphaConviction.BUY)][:10]
        top_risks = [p.ticker for p in profiles if p.conviction in (AlphaConviction.SELL, AlphaConviction.STRONG_SELL)][:5]

        return MultiAlphaResult(
            rankings=profiles, heatmap=heatmap,
            top_opportunities=top_opps, top_risks=top_risks,
            total_analyzed=len(profiles),
        )

    def _classify_conviction(self, score: float, bullish: int, bearish: int) -> AlphaConviction:
        if score >= 80 and bullish >= 4: return AlphaConviction.STRONG_BUY
        if score >= 65: return AlphaConviction.BUY
        if score >= 40: return AlphaConviction.NEUTRAL
        if score >= 25 or bearish >= 3: return AlphaConviction.SELL
        return AlphaConviction.STRONG_SELL


def _clamp(v, lo=0, hi=100) -> float:
    try: return min(max(float(v), lo), hi)
    except (ValueError, TypeError): return 50.0
