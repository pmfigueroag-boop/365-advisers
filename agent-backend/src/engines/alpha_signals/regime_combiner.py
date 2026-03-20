"""
src/engines/alpha_signals/regime_combiner.py
──────────────────────────────────────────────────────────────────────────────
#8: Regime-Conditioned IC Tables.

Instead of just tech/non-tech split, applies different IC weights based on
the current QVF market regime (Growth, Value, Contraction, Crisis).

Architecture:
  - 4 IC weight tables: one per QVF regime
  - combine() checks current regime and selects appropriate table
  - Falls back to sector-based tables if regime is unknown

Regime definitions (from QVF engine):
  - GROWTH:      VIX < 20, SPY above SMA200, uptrending
  - VALUE:       VIX 15-25, SPY near SMA200, rotational
  - CONTRACTION: VIX 25-35, SPY below SMA200, defensive
  - CRISIS:      VIX > 35, sharp drawdowns, risk-off
"""

from __future__ import annotations

import logging
from copy import copy
from enum import Enum

from src.engines.alpha_signals.models import (
    EvaluatedSignal,
    CompositeScore,
    SignalLevel,
    ConfidenceLevel,
)
from src.engines.alpha_signals.combiner import (
    SignalCombiner,
    _IC_WEIGHTS_TECH,
    _IC_WEIGHTS_NON_TECH,
    _REDUNDANCY_CLUSTERS,
    _DEFAULT_IC_WEIGHT,
    STRONG_BUY_THRESHOLD,
    BUY_THRESHOLD,
)

logger = logging.getLogger("365advisers.alpha_signals.regime_combiner")


class MarketRegime(str, Enum):
    GROWTH = "growth"
    VALUE = "value"
    CONTRACTION = "contraction"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


# ── Regime IC adjustments ────────────────────────────────────────────────────
# These are MULTIPLIERS applied to the base sector IC weights.
# Rationale: certain signals perform differently in different regimes.

_REGIME_ADJUSTMENTS: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.GROWTH: {
        # Momentum thrives in growth regimes
        "momentum.golden_cross": 0.5,        # less contrarian alpha in growth
        "momentum.price_above_ema20": 1.5,   # trend-following works
        "growth.operating_leverage": 1.3,
        "growth.rule_of_40": 1.3,
        "pricecycle.deep_pullback": 1.5,      # dip-buying in bull markets
        "risk.death_cross": 0.3,              # less signal in uptrend
        # Macro signals amplified
        "macro.credit_spread_tightening": 1.5,
        # Value signals weaker
        "value.pe_low": 0.7,
        "value.ev_ebitda_low": 0.7,
    },

    MarketRegime.VALUE: {
        # Value signals shine in rotational markets
        "value.pe_low": 1.5,
        "value.ev_ebitda_low": 1.5,
        "value.ev_revenue_low": 1.5,
        "value.ebit_ev_high": 1.5,
        "value.fcf_yield_high": 1.3,
        # Quality becomes important
        "quality.piotroski_f_score": 1.5,
        "quality.accruals_quality": 1.3,
        # Momentum neutral
        "momentum.golden_cross": 1.0,
        "momentum.price_above_ema20": 0.7,
    },

    MarketRegime.CONTRACTION: {
        # Defensive / quality signals dominate
        "quality.interest_coverage_fortress": 2.0,
        "quality.low_leverage": 1.5,
        "quality.stable_margins": 1.5,
        "value.div_yield_vs_hist": 1.5,
        "value.shareholder_yield": 1.5,
        # Risk signals amplified (bearish → more predictive)
        "risk.death_cross": 1.5,
        "risk.high_leverage": 1.5,
        # Momentum weakened
        "momentum.golden_cross": 0.5,
        "momentum.volume_surge": 0.5,
        # Credit spread becomes very important
        "macro.credit_spread_widening": 2.0,
        "macro.credit_spread_tightening": 0.5,
    },

    MarketRegime.CRISIS: {
        # Everything reverses — contrarian alpha is maximum
        "pricecycle.deep_pullback": 2.5,      # buying panic = maximum alpha
        "pricecycle.oversold_z": 2.0,
        "risk.death_cross": 2.0,               # strongest contrarian signal
        "flow.short_interest_high": 2.0,       # short squeeze setups
        # Quality is a lifeline
        "quality.interest_coverage_fortress": 2.5,
        "quality.piotroski_f_score": 2.0,
        # Growth/momentum becomes noise
        "growth.operating_leverage": 0.3,
        "momentum.price_above_ema20": 0.3,
        "momentum.golden_cross": 0.3,
        # Macro signals dominate
        "macro.credit_spread_widening": 3.0,
        "macro.credit_spread_tightening": 2.0,
    },
}


class RegimeCombiner:
    """
    #8: Regime-Conditioned Signal Combiner.

    Wraps the base SignalCombiner and applies regime-specific IC adjustments.

    Usage:
        combiner = RegimeCombiner()
        score = combiner.combine(signals, sector="Technology", regime=MarketRegime.GROWTH)
    """

    def __init__(self):
        self._base_combiner = SignalCombiner()

    def combine(
        self,
        signals: list[EvaluatedSignal],
        sector: str = "",
        regime: MarketRegime = MarketRegime.UNKNOWN,
    ) -> CompositeScore:
        """
        Combine signals with regime-adjusted IC weights.

        Falls back to base combiner if regime is UNKNOWN.
        """
        if regime == MarketRegime.UNKNOWN:
            return self._base_combiner.combine(signals, sector=sector)

        # Get regime adjustments
        adjustments = _REGIME_ADJUSTMENTS.get(regime, {})

        if not adjustments:
            return self._base_combiner.combine(signals, sector=sector)

        # Apply adjustments to the base combiner's _get_ic_weight logic
        # We compute the score manually with adjusted weights
        from src.engines.alpha_signals.combiner import _classify_sector

        sector_type = _classify_sector(sector)
        base_weights = _IC_WEIGHTS_TECH if sector_type == "tech" else _IC_WEIGHTS_NON_TECH

        fired = [s for s in signals if s.fired]
        if not fired:
            return CompositeScore(
                composite_score=0.0,
                level=SignalLevel.HOLD,
                confidence=ConfidenceLevel.LOW,
                fired_count=0,
                total_count=len(signals),
                top_signals=[],
                category_scores=[],
                explanation=f"Regime={regime.value}, no signals fired",
            )

        # Deduplicate via redundancy clusters
        seen_clusters: set[int] = set()
        deduplicated: list[EvaluatedSignal] = []
        for s in fired:
            cluster_id = None
            for i, cluster in enumerate(_REDUNDANCY_CLUSTERS):
                if s.signal_id in cluster:
                    cluster_id = i
                    break
            if cluster_id is not None and cluster_id in seen_clusters:
                continue
            if cluster_id is not None:
                seen_clusters.add(cluster_id)
            deduplicated.append(s)

        # Compute IC-weighted score with regime adjustments
        total_score = 0.0
        weight_sum = 0.0

        for s in deduplicated:
            base_ic = base_weights.get(s.signal_id, _DEFAULT_IC_WEIGHT)
            regime_mult = adjustments.get(s.signal_id, 1.0)
            adjusted_ic = base_ic * regime_mult

            if adjusted_ic != 0:
                total_score += adjusted_ic * s.confidence
                weight_sum += abs(adjusted_ic)

        normalized = total_score / weight_sum if weight_sum > 0 else 0.0
        # Scale to 0-1
        composite = max(0, min(1, (normalized + 0.5)))

        if composite >= STRONG_BUY_THRESHOLD:
            level = SignalLevel.STRONG_BUY
        elif composite >= BUY_THRESHOLD:
            level = SignalLevel.BUY
        else:
            level = SignalLevel.HOLD

        confidence = ConfidenceLevel.HIGH if composite >= 0.4 else (
            ConfidenceLevel.MEDIUM if composite >= 0.2 else ConfidenceLevel.LOW
        )

        return CompositeScore(
            composite_score=round(composite, 4),
            level=level,
            confidence=confidence,
            fired_count=len(fired),
            total_count=len(signals),
            top_signals=[s.signal_id for s in deduplicated[:5]],
            category_scores=[],
            explanation=(
                f"Regime={regime.value} | sector={sector_type} | "
                f"fired={len(fired)} → dedup={len(deduplicated)} | "
                f"score={composite:.3f}"
            ),
        )

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
