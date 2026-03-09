"""
src/engines/investment_brain/regime_detector.py
──────────────────────────────────────────────────────────────────────────────
Market Regime Detector — identifies the current macroeconomic regime by
synthesising macro indicators, volatility conditions, and index behaviour.

Consumes: AlphaMacroEngine dashboard, AlphaVolatilityEngine dashboard.
Output:   RegimeClassification with 6 possible regimes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.investment_brain.models import (
    MarketRegime,
    RegimeClassification,
    RegimeFactor,
)

logger = logging.getLogger("365advisers.investment_brain.regime")


class RegimeDetector:
    """
    Detects the current market regime from macro and volatility signals.

    Usage::

        detector = RegimeDetector()
        classification = detector.detect(macro_dashboard, vol_dashboard, index_data)
    """

    # ── Regime scoring matrix ────────────────────────────────────────────
    # Each function returns (regime, score) tuples for a given condition

    def detect(
        self,
        macro_data: dict | None = None,
        vol_data: dict | None = None,
        index_data: dict | None = None,
    ) -> RegimeClassification:
        """
        Classify the current market regime.

        Parameters
        ----------
        macro_data : dict | None
            Macro indicators: gdp_growth, inflation, unemployment,
            interest_rate, yield_curve_spread, pmi, consumer_confidence,
            credit_spread, m2_growth
        vol_data : dict | None
            Volatility data: vix_current, iv_rank, term_structure_slope
        index_data : dict | None
            Index behaviour: sp500_return_1m, sp500_return_3m, sp500_trend
        """
        macro = macro_data or {}
        vol = vol_data or {}
        idx = index_data or {}

        factors: list[RegimeFactor] = []
        scores: dict[MarketRegime, float] = {r: 0.0 for r in MarketRegime}

        # ── Macro indicators ────────────────────────────────────────────
        gdp = _f(macro.get("gdp_growth"))
        if gdp is not None:
            if gdp > 2.5:
                scores[MarketRegime.EXPANSION] += 25
                factors.append(RegimeFactor(name="GDP Growth", value=gdp, signal="bullish", weight=0.20, description=f"Strong growth at {gdp:.1f}%"))
            elif gdp > 0.5:
                scores[MarketRegime.SLOWDOWN] += 15
                scores[MarketRegime.RECOVERY] += 10
                factors.append(RegimeFactor(name="GDP Growth", value=gdp, signal="neutral", weight=0.20, description=f"Moderate growth at {gdp:.1f}%"))
            else:
                scores[MarketRegime.RECESSION] += 25
                factors.append(RegimeFactor(name="GDP Growth", value=gdp, signal="bearish", weight=0.20, description=f"Weak/negative growth at {gdp:.1f}%"))

        inflation = _f(macro.get("inflation"))
        if inflation is not None:
            if inflation > 5.0:
                scores[MarketRegime.SLOWDOWN] += 15
                scores[MarketRegime.HIGH_VOLATILITY] += 10
                factors.append(RegimeFactor(name="Inflation", value=inflation, signal="bearish", weight=0.15, description=f"Elevated inflation at {inflation:.1f}%"))
            elif inflation > 2.5:
                scores[MarketRegime.EXPANSION] += 5
                factors.append(RegimeFactor(name="Inflation", value=inflation, signal="neutral", weight=0.15, description=f"Moderate inflation at {inflation:.1f}%"))
            else:
                scores[MarketRegime.RECOVERY] += 10
                scores[MarketRegime.LIQUIDITY_EXPANSION] += 10
                factors.append(RegimeFactor(name="Inflation", value=inflation, signal="bullish", weight=0.15, description=f"Low inflation at {inflation:.1f}%"))

        interest_rate = _f(macro.get("interest_rate"))
        if interest_rate is not None:
            if interest_rate > 5.0:
                scores[MarketRegime.SLOWDOWN] += 15
                factors.append(RegimeFactor(name="Interest Rate", value=interest_rate, signal="bearish", weight=0.15, description=f"High rates at {interest_rate:.1f}%"))
            elif interest_rate < 2.0:
                scores[MarketRegime.LIQUIDITY_EXPANSION] += 20
                scores[MarketRegime.RECOVERY] += 10
                factors.append(RegimeFactor(name="Interest Rate", value=interest_rate, signal="bullish", weight=0.15, description=f"Low rates at {interest_rate:.1f}%"))
            else:
                scores[MarketRegime.EXPANSION] += 5
                factors.append(RegimeFactor(name="Interest Rate", value=interest_rate, signal="neutral", weight=0.15, description=f"Neutral rates at {interest_rate:.1f}%"))

        unemployment = _f(macro.get("unemployment"))
        if unemployment is not None:
            if unemployment > 7.0:
                scores[MarketRegime.RECESSION] += 20
                factors.append(RegimeFactor(name="Unemployment", value=unemployment, signal="bearish", weight=0.10, description=f"High unemployment at {unemployment:.1f}%"))
            elif unemployment < 4.5:
                scores[MarketRegime.EXPANSION] += 15
                factors.append(RegimeFactor(name="Unemployment", value=unemployment, signal="bullish", weight=0.10, description=f"Low unemployment at {unemployment:.1f}%"))
            else:
                factors.append(RegimeFactor(name="Unemployment", value=unemployment, signal="neutral", weight=0.10, description=f"Moderate unemployment at {unemployment:.1f}%"))

        pmi = _f(macro.get("pmi"))
        if pmi is not None:
            if pmi > 55:
                scores[MarketRegime.EXPANSION] += 15
                factors.append(RegimeFactor(name="PMI", value=pmi, signal="bullish", weight=0.10, description=f"Expansionary PMI at {pmi:.1f}"))
            elif pmi < 48:
                scores[MarketRegime.RECESSION] += 15
                scores[MarketRegime.SLOWDOWN] += 10
                factors.append(RegimeFactor(name="PMI", value=pmi, signal="bearish", weight=0.10, description=f"Contractionary PMI at {pmi:.1f}"))
            else:
                factors.append(RegimeFactor(name="PMI", value=pmi, signal="neutral", weight=0.10, description=f"Neutral PMI at {pmi:.1f}"))

        yield_curve = _f(macro.get("yield_curve_spread"))
        if yield_curve is not None:
            if yield_curve < -0.5:
                scores[MarketRegime.RECESSION] += 20
                factors.append(RegimeFactor(name="Yield Curve", value=yield_curve, signal="bearish", weight=0.10, description="Inverted yield curve — recession signal"))
            elif yield_curve > 1.5:
                scores[MarketRegime.RECOVERY] += 15
                scores[MarketRegime.EXPANSION] += 5
                factors.append(RegimeFactor(name="Yield Curve", value=yield_curve, signal="bullish", weight=0.10, description="Steep yield curve — growth signal"))

        m2_growth = _f(macro.get("m2_growth"))
        if m2_growth is not None:
            if m2_growth > 8.0:
                scores[MarketRegime.LIQUIDITY_EXPANSION] += 25
                factors.append(RegimeFactor(name="M2 Growth", value=m2_growth, signal="bullish", weight=0.10, description=f"Rapid money supply expansion at {m2_growth:.1f}%"))
            elif m2_growth < 0:
                scores[MarketRegime.SLOWDOWN] += 10
                factors.append(RegimeFactor(name="M2 Growth", value=m2_growth, signal="bearish", weight=0.10, description="Money supply contraction"))

        # ── Volatility indicators ───────────────────────────────────────
        vix = _f(vol.get("vix_current"))
        if vix is not None:
            if vix > 30:
                scores[MarketRegime.HIGH_VOLATILITY] += 30
                scores[MarketRegime.RECESSION] += 10
                factors.append(RegimeFactor(name="VIX", value=vix, signal="bearish", weight=0.15, description=f"Extreme volatility — VIX at {vix:.1f}"))
            elif vix > 20:
                scores[MarketRegime.HIGH_VOLATILITY] += 15
                scores[MarketRegime.SLOWDOWN] += 5
                factors.append(RegimeFactor(name="VIX", value=vix, signal="bearish", weight=0.15, description=f"Elevated volatility — VIX at {vix:.1f}"))
            elif vix < 15:
                scores[MarketRegime.EXPANSION] += 10
                scores[MarketRegime.LIQUIDITY_EXPANSION] += 5
                factors.append(RegimeFactor(name="VIX", value=vix, signal="bullish", weight=0.15, description=f"Low volatility — VIX at {vix:.1f}"))

        iv_rank = _f(vol.get("iv_rank"))
        if iv_rank is not None and iv_rank > 80:
            scores[MarketRegime.HIGH_VOLATILITY] += 10
            factors.append(RegimeFactor(name="IV Rank", value=iv_rank, signal="bearish", weight=0.05, description=f"IV Rank elevated at {iv_rank:.0f}th percentile"))

        # ── Index behaviour ─────────────────────────────────────────────
        sp_1m = _f(idx.get("sp500_return_1m"))
        sp_3m = _f(idx.get("sp500_return_3m"))
        if sp_1m is not None and sp_3m is not None:
            if sp_1m > 3 and sp_3m > 5:
                scores[MarketRegime.EXPANSION] += 10
                factors.append(RegimeFactor(name="S&P 500 Trend", value=sp_3m, signal="bullish", weight=0.05, description="Strong index momentum"))
            elif sp_1m < -5 and sp_3m < -10:
                scores[MarketRegime.RECESSION] += 10
                scores[MarketRegime.HIGH_VOLATILITY] += 5
                factors.append(RegimeFactor(name="S&P 500 Trend", value=sp_3m, signal="bearish", weight=0.05, description="Significant index decline"))

        # ── Classify ────────────────────────────────────────────────────
        total = sum(scores.values()) or 1.0
        probabilities = {r.value: round(s / total, 3) for r, s in scores.items()}
        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        confidence = round(scores[best] / total, 3) if total > 0 else 0.5

        summary = self._generate_summary(best, factors)

        return RegimeClassification(
            regime=best,
            confidence=confidence,
            probabilities=probabilities,
            contributing_factors=factors,
            summary=summary,
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _generate_summary(regime: MarketRegime, factors: list[RegimeFactor]) -> str:
        descriptions = {
            MarketRegime.EXPANSION: "Economy in expansion phase with strong growth and favorable conditions.",
            MarketRegime.SLOWDOWN: "Economic growth decelerating with tightening conditions.",
            MarketRegime.RECESSION: "Recessionary conditions with weakening growth and elevated stress.",
            MarketRegime.RECOVERY: "Early recovery phase with improving conditions from trough.",
            MarketRegime.HIGH_VOLATILITY: "Elevated volatility regime with heightened market stress.",
            MarketRegime.LIQUIDITY_EXPANSION: "Abundant liquidity conditions with accommodative monetary policy.",
        }
        base = descriptions.get(regime, "")
        key_factors = [f.name for f in factors if f.signal != "neutral"][:3]
        if key_factors:
            base += f" Key drivers: {', '.join(key_factors)}."
        return base


def _f(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
