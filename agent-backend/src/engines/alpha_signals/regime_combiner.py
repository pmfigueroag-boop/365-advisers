"""
src/engines/alpha_signals/regime_combiner.py
──────────────────────────────────────────────────────────────────────────────
#8: Regime-Conditioned IC Tables (V4 Evidence-Based).

Applies regime-specific IC adjustments on TOP of the evidence-based IC
tables from combiner.py.

IMPORTANT: All regime multipliers are set to 1.0 (neutral) because none
were empirically validated in the backtest.  The sector-based combiner
already generates +4.86% excess return — adding unvalidated regime tilts
would introduce unquantified risk.

Architecture:
  - combine() with regime=UNKNOWN → delegates to base SignalCombiner (V4)
  - combine() with specific regime → same as UNKNOWN (multipliers are 1.0)
  - detect_regime() still works for classification purposes

When regime-specific backtest data becomes available, the multipliers
in _REGIME_ADJUSTMENTS can be updated with evidence.
"""

from __future__ import annotations

import logging
from enum import Enum

from src.engines.alpha_signals.models import (
    EvaluatedSignal,
    CompositeScore,
    SignalProfile,
    SignalLevel,
    ConfidenceLevel,
)
from src.engines.alpha_signals.combiner import SignalCombiner

logger = logging.getLogger("365advisers.alpha_signals.regime_combiner")


class MarketRegime(str, Enum):
    GROWTH = "growth"
    VALUE = "value"
    CONTRACTION = "contraction"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


# ── Regime IC adjustments ────────────────────────────────────────────────────
# All set to 1.0 (neutral) — no empirical validation available.
# Kept as structure for future evidence-based calibration.

_REGIME_ADJUSTMENTS: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.GROWTH: {},       # no adjustments until validated
    MarketRegime.VALUE: {},
    MarketRegime.CONTRACTION: {},
    MarketRegime.CRISIS: {},
}


class RegimeCombiner:
    """
    #8: Regime-Conditioned Signal Combiner (Evidence-Based V4).

    Currently delegates entirely to the base SignalCombiner since regime
    adjustments are not empirically validated.

    Usage:
        combiner = RegimeCombiner()
        score = combiner.combine(profile, sector="Technology", regime=MarketRegime.GROWTH)
    """

    def __init__(self):
        self._base_combiner = SignalCombiner()

    def combine(
        self,
        profile: SignalProfile,
        sector: str = "",
        regime: MarketRegime = MarketRegime.UNKNOWN,
    ) -> CompositeScore:
        """
        Combine signals with optional regime context.

        Currently all regimes delegate to the base combiner since
        regime-specific weights are not empirically validated.
        """
        # Log regime for observability, but don't apply adjustments
        if regime != MarketRegime.UNKNOWN:
            logger.info(
                f"REGIME COMBINER: regime={regime.value}, sector={sector} "
                f"(using base combiner — regime adjustments not validated)"
            )

        return self._base_combiner.combine(profile, sector=sector)

    @staticmethod
    def detect_regime(
        vix: float | None = None,
        spy_vs_sma200: float | None = None,
        drawdown_pct: float | None = None,
    ) -> MarketRegime:
        """
        Classify current market regime from observable factors.

        Parameters
        ----------
        vix : float | None
            Current VIX level.
        spy_vs_sma200 : float | None
            SPY price / SMA200 ratio (> 1.0 = above).
        drawdown_pct : float | None
            Current max drawdown from peak (e.g. -0.15 = 15% drawdown).
        """
        if vix is None:
            return MarketRegime.UNKNOWN

        # Crisis: VIX > 35 or drawdown > 20%
        if vix > 35 or (drawdown_pct is not None and drawdown_pct < -0.20):
            return MarketRegime.CRISIS

        # Contraction: VIX 25-35 or SPY below SMA200
        if vix > 25 or (spy_vs_sma200 is not None and spy_vs_sma200 < 0.97):
            return MarketRegime.CONTRACTION

        # Value: VIX 15-25, SPY near SMA200
        if spy_vs_sma200 is not None and spy_vs_sma200 < 1.03:
            return MarketRegime.VALUE

        # Growth: VIX < 20, SPY above SMA200
        return MarketRegime.GROWTH
