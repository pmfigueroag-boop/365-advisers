"""
src/engines/technical/purified_scoring.py
──────────────────────────────────────────────────────────────────────────────
Purified Technical Score — uses ONLY the 11 indicators with empirically
validated predictive power (p<0.05 Spearman vs T+20d forward returns).

Architecture:
  VOL  (50%): ATR%, realized_vol_20d, BB_width_pct, BB_upper_dist
  VOLUME (20%): volume_surprise, relative_volume, effort_result
  REGIME (30%): ADX, SMA50/200_spread, dist_SMA200%, DI_spread

ELIMINATED: RSI, Stochastic, MACD, MFI, 52w high, Mean Reversion Z.

Scoring: z-score normalisation → sigmoid → ρ-weighted average → 0-10.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field as dc_field

logger = logging.getLogger("365advisers.engines.technical.purified_scoring")


# ─── Indicator Definitions ───────────────────────────────────────────────────

_INDICATORS = {
    # VOL GROUP — all "lower is better"
    "atr_pct":       {"group": "vol",    "rho": -0.243, "lower_better": True},
    "realized_vol":  {"group": "vol",    "rho": -0.184, "lower_better": True},
    "bb_width_pct":  {"group": "vol",    "rho": -0.157, "lower_better": True},
    "bb_upper_dist": {"group": "vol",    "rho": -0.121, "lower_better": True},
    # VOLUME GROUP — mixed direction
    "vol_surprise":  {"group": "volume", "rho": +0.123, "lower_better": False},
    "rel_volume":    {"group": "volume", "rho": +0.100, "lower_better": False},
    "effort_result": {"group": "volume", "rho": -0.076, "lower_better": True},
    # REGIME GROUP — all "lower is better"
    "adx":           {"group": "regime", "rho": -0.144, "lower_better": True},
    "sma_spread":    {"group": "regime", "rho": -0.136, "lower_better": True},
    "dist_sma200":   {"group": "regime", "rho": -0.083, "lower_better": True},
    "di_spread":     {"group": "regime", "rho": -0.089, "lower_better": True},
}

_GROUP_WEIGHTS = {"vol": 0.50, "volume": 0.20, "regime": 0.30}

# Pre-computed IS normalisation stats (from 94-stock × 3Y training set)
# These can be recalibrated periodically using a walk-forward routine.
_NORM_STATS: dict[str, dict[str, float]] = {
    "atr_pct":       {"mean": 2.0,   "std": 1.2},
    "realized_vol":  {"mean": 0.25,  "std": 0.12},
    "bb_width_pct":  {"mean": 7.5,   "std": 4.0},
    "bb_upper_dist": {"mean": 2.5,   "std": 3.5},
    "vol_surprise":  {"mean": 1.0,   "std": 0.8},
    "rel_volume":    {"mean": 1.0,   "std": 0.6},
    "effort_result": {"mean": 1.0,   "std": 0.5},
    "adx":           {"mean": 22.0,  "std": 10.0},
    "sma_spread":    {"mean": 0.0,   "std": 5.0},
    "dist_sma200":   {"mean": 5.0,   "std": 12.0},
    "di_spread":     {"mean": 0.0,   "std": 15.0},
}


# ─── Outputs ──────────────────────────────────────────────────────────────────

@dataclass
class PurifiedGroupScore:
    """Score for one indicator group (vol, volume, regime)."""
    name: str
    score: float  # 0-10
    weight: float
    indicators_used: int = 0


@dataclass
class PurifiedTechScore:
    """Complete output of the Purified Technical Scoring Engine."""
    aggregate: float  # 0-10
    signal: str  # STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
    strength: str  # Strong / Moderate / Weak
    confidence: float  # 0-1 (fraction of indicators available)
    group_scores: list[PurifiedGroupScore] = dc_field(default_factory=list)
    evidence: list[str] = dc_field(default_factory=list)
    indicators_available: int = 0
    indicators_total: int = 11


# ─── Core Engine ──────────────────────────────────────────────────────────────

def _sigmoid_01(z: float) -> float:
    """Sigmoid mapping z → (0, 1)."""
    z = max(min(z, 10.0), -10.0)
    return 1.0 / (1.0 + math.exp(-z))


def _derive_signal(score: float) -> tuple[str, str]:
    """Convert 0-10 aggregate to (signal, strength)."""
    if score >= 7.5:
        return "STRONG_BUY", "Strong"
    if score >= 6.0:
        return "BUY", "Moderate"
    if score >= 4.0:
        return "HOLD", "Weak"
    if score >= 2.5:
        return "SELL", "Moderate"
    return "STRONG_SELL", "Strong"


class PurifiedScoringEngine:
    """
    Purified Technical Scoring Engine.

    Uses only the 11 indicators with validated predictive power.
    Each indicator is z-scored, passed through a sigmoid, and weighted
    proportionally to its Spearman |ρ| with T+20d forward returns.
    """

    @staticmethod
    def extract_indicators(
        indicator_result,
        features,
    ) -> dict[str, float | None]:
        """
        Extract the 11 purified indicators from the existing
        IndicatorEngine output and TechnicalFeatureSet.

        Parameters
        ----------
        indicator_result : IndicatorResult from ``IndicatorEngine.compute()``
        features : TechnicalFeatureSet

        Returns
        -------
        dict of indicator name → value (or None if unavailable)
        """
        price = features.current_price or 1.0
        sma200 = features.sma_200 or 1.0
        sma50 = features.sma_50 or 1.0
        atr = features.atr or 0.0
        bb_upper = features.bb_upper or 0.0

        # Volatility group
        atr_pct = (atr / price * 100.0) if price > 0 else None
        realized_vol = getattr(indicator_result.volatility, "realized_vol_20d", None)
        bb_width_pct = None
        if features.bb_upper and features.bb_lower and price > 0:
            bb_width_pct = ((features.bb_upper - features.bb_lower) / price) * 100.0
        bb_upper_dist = ((bb_upper - price) / price * 100.0) if price > 0 else None

        # Volume group
        vol_surprise = getattr(indicator_result.volume, "volume_surprise", None)
        rel_volume = getattr(indicator_result.volume, "volume_vs_avg", None)
        effort_result = getattr(indicator_result.volume, "effort_result_ratio", None)

        # Regime group
        adx = getattr(features, "adx", None) or 20.0
        plus_di = getattr(features, "plus_di", None) or 20.0
        minus_di = getattr(features, "minus_di", None) or 20.0
        sma_spread = None
        if sma50 > 0 and sma200 > 0:
            sma_spread = ((sma50 - sma200) / sma200) * 100.0
        dist_sma200 = ((price - sma200) / sma200 * 100.0) if sma200 > 0 else None
        di_spread = plus_di - minus_di

        return {
            "atr_pct": atr_pct,
            "realized_vol": realized_vol,
            "bb_width_pct": bb_width_pct,
            "bb_upper_dist": bb_upper_dist,
            "vol_surprise": vol_surprise,
            "rel_volume": rel_volume,
            "effort_result": effort_result,
            "adx": adx,
            "sma_spread": sma_spread,
            "dist_sma200": dist_sma200,
            "di_spread": di_spread,
        }

    @classmethod
    def compute(
        cls,
        indicator_result,
        features,
    ) -> PurifiedTechScore:
        """
        Compute the Purified Technical Score.

        Parameters
        ----------
        indicator_result : IndicatorResult from ``IndicatorEngine.compute()``
        features : TechnicalFeatureSet

        Returns
        -------
        PurifiedTechScore with 0-10 aggregate, signal, group breakdown.
        """
        raw = cls.extract_indicators(indicator_result, features)
        evidence: list[str] = []

        # Score each indicator and accumulate by group
        group_scores: dict[str, list[float]] = {"vol": [], "volume": [], "regime": []}
        group_weights: dict[str, list[float]] = {"vol": [], "volume": [], "regime": []}
        available = 0

        for ind_name, meta in _INDICATORS.items():
            val = raw.get(ind_name)
            if val is None:
                continue

            stats = _NORM_STATS.get(ind_name, {"mean": 0, "std": 1})
            if stats["std"] <= 0:
                continue

            available += 1
            z = (val - stats["mean"]) / stats["std"]
            z = max(min(z, 3.0), -3.0)

            # Invert if lower_better so that low values → high score
            if meta["lower_better"]:
                z = -z

            # Sigmoid → 0-10
            sub_score = _sigmoid_01(z * 1.5) * 10.0
            w = abs(meta["rho"])

            group_scores[meta["group"]].append(sub_score * w)
            group_weights[meta["group"]].append(w)

            # Evidence for notable signals
            if sub_score >= 7.0:
                evidence.append(f"✅ {ind_name}={val:.2f} → {sub_score:.1f}/10 (bullish)")
            elif sub_score <= 3.0:
                evidence.append(f"⚠ {ind_name}={val:.2f} → {sub_score:.1f}/10 (bearish)")

        # Weighted average within each group, then across groups
        group_results: list[PurifiedGroupScore] = []
        final_score = 0.0
        total_group_weight = 0.0

        for group_name, gw in _GROUP_WEIGHTS.items():
            gs = group_scores[group_name]
            gw_sums = group_weights[group_name]
            if gs and gw_sums:
                group_avg = sum(gs) / sum(gw_sums)
                final_score += group_avg * gw
                total_group_weight += gw
                group_results.append(PurifiedGroupScore(
                    name=group_name, score=round(group_avg, 2),
                    weight=gw, indicators_used=len(gs),
                ))
            else:
                group_results.append(PurifiedGroupScore(
                    name=group_name, score=5.0, weight=gw, indicators_used=0,
                ))

        aggregate = (final_score / total_group_weight) if total_group_weight > 0 else 5.0
        aggregate = max(0.0, min(10.0, round(aggregate, 2)))

        signal, strength = _derive_signal(aggregate)
        confidence = available / 11.0

        return PurifiedTechScore(
            aggregate=aggregate,
            signal=signal,
            strength=strength,
            confidence=round(confidence, 2),
            group_scores=group_results,
            evidence=evidence,
            indicators_available=available,
        )
