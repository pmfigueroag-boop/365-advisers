"""
src/engines/technical/mtf_scorer.py
─────────────────────────────────────────────────────────────────────────────
Multi-Timeframe Scorer — aggregates technical scores across multiple
timeframes (1H, 4H, 1D, 1W) with agreement/conflict logic.

Each timeframe's indicators are processed through the same IndicatorEngine
and ScoringEngine, then weighted by a timeframe importance hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.engines.technical.indicators import IndicatorEngine
from src.engines.technical.scoring import ScoringEngine, TechnicalScore


# ─── Timeframe weights ───────────────────────────────────────────────────────

MTF_WEIGHTS = {
    "1h":  0.10,   # noisy, low weight
    "4h":  0.20,   # swing trading
    "1d":  0.40,   # primary timeframe
    "1w":  0.30,   # macro context
}


# ─── Result dataclass ────────────────────────────────────────────────────────

@dataclass
class TimeframeScore:
    timeframe: str
    score: float
    signal: str
    trend_status: str
    momentum_status: str


@dataclass
class MTFResult:
    mtf_aggregate: float            # 0–10 weighted average
    mtf_signal: str                 # derived from aggregate
    agreement_level: Literal["STRONG", "MODERATE", "WEAK"]
    agreement_count: int            # how many TFs agree on direction
    timeframe_scores: list[TimeframeScore] = field(default_factory=list)
    bonus_applied: float = 0.0      # agreement/conflict adjustment


# ─── Scorer ──────────────────────────────────────────────────────────────────

class MultiTimeframeScorer:
    """
    Aggregate technical scores from multiple timeframes into a single
    MTF-adjusted score.

    Agreement bonus: if ≥3 of 4 timeframes agree on signal direction → +0.5
    Conflict penalty: if 1H and 1W conflict → -0.3
    """

    @staticmethod
    def compute(
        multi_tf_data: dict[str, dict],
        regime_adjustments: dict[str, float] | None = None,
    ) -> MTFResult:
        """
        Args:
            multi_tf_data: dict keyed by timeframe label (e.g. "1h", "4h", "1d", "1w"),
                           each value is a tech_data dict compatible with IndicatorEngine.
            regime_adjustments: optional regime weight multipliers (from daily analysis).

        Returns:
            MTFResult with weighted aggregate, agreement analysis, and per-TF breakdown.
        """
        tf_scores: list[TimeframeScore] = []
        weighted_sum = 0.0
        weight_sum = 0.0

        for tf_key, weight in MTF_WEIGHTS.items():
            td = multi_tf_data.get(tf_key)
            if not td:
                continue

            # Run IndicatorEngine
            indicators = IndicatorEngine.compute(td)

            # Run ScoringEngine (with regime adjustments for 1D only)
            adj = regime_adjustments if tf_key == "1d" else None
            score = ScoringEngine.compute(indicators, regime_adjustments=adj)

            tf_scores.append(TimeframeScore(
                timeframe=tf_key,
                score=score.aggregate,
                signal=score.signal,
                trend_status=indicators.trend.status,
                momentum_status=indicators.momentum.status,
            ))

            weighted_sum += score.aggregate * weight
            weight_sum += weight

        if weight_sum == 0 or not tf_scores:
            return MTFResult(
                mtf_aggregate=5.0,
                mtf_signal="NEUTRAL",
                agreement_level="WEAK",
                agreement_count=0,
            )

        mtf_aggregate = weighted_sum / weight_sum

        # ── Agreement analysis ───────────────────────────────────────────
        signals = [ts.signal for ts in tf_scores]
        bullish_count = sum(1 for s in signals if s in ("STRONG_BUY", "BUY"))
        bearish_count = sum(1 for s in signals if s in ("STRONG_SELL", "SELL"))
        neutral_count = sum(1 for s in signals if s == "NEUTRAL")

        agreement_count = max(bullish_count, bearish_count, neutral_count)

        # Agreement bonus / conflict penalty
        bonus = 0.0
        if agreement_count >= 3:
            bonus = 0.5 if bullish_count >= 3 else (-0.5 if bearish_count >= 3 else 0.0)

        # Short-term vs long-term conflict
        tf_map = {ts.timeframe: ts.signal for ts in tf_scores}
        short = tf_map.get("1h", "")
        long_ = tf_map.get("1w", "")
        if short and long_:
            short_bull = short in ("STRONG_BUY", "BUY")
            short_bear = short in ("STRONG_SELL", "SELL")
            long_bull = long_ in ("STRONG_BUY", "BUY")
            long_bear = long_ in ("STRONG_SELL", "SELL")
            if (short_bull and long_bear) or (short_bear and long_bull):
                bonus -= 0.3  # short/long conflict = uncertainty

        mtf_aggregate = round(mtf_aggregate + bonus, 2)
        mtf_aggregate = max(0.0, min(10.0, mtf_aggregate))

        # Agreement quality
        if agreement_count >= 3:
            agreement_level = "STRONG"
        elif agreement_count >= 2:
            agreement_level = "MODERATE"
        else:
            agreement_level = "WEAK"

        # Derive signal from MTF aggregate
        if mtf_aggregate >= 8.0:
            mtf_signal = "STRONG_BUY"
        elif mtf_aggregate >= 6.5:
            mtf_signal = "BUY"
        elif mtf_aggregate >= 4.5:
            mtf_signal = "NEUTRAL"
        elif mtf_aggregate >= 3.0:
            mtf_signal = "SELL"
        else:
            mtf_signal = "STRONG_SELL"

        return MTFResult(
            mtf_aggregate=mtf_aggregate,
            mtf_signal=mtf_signal,
            agreement_level=agreement_level,
            agreement_count=agreement_count,
            timeframe_scores=tf_scores,
            bonus_applied=round(bonus, 2),
        )
