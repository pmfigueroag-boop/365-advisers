"""
src/engines/super_alpha/factors/momentum.py
──────────────────────────────────────────────────────────────────────────────
Momentum Factor Engine — detects positive trend persistence using
multi-horizon return analysis.

Variables: 3m returns, 6m returns, 12m returns, Price/SMA200 ratio
Weights:   [0.20, 0.30, 0.35, 0.15]
Output:    0–100 Momentum Score
"""

from __future__ import annotations

import logging
import math

from src.engines.super_alpha.models import (
    FactorName, FactorScore, VariableContribution,
)

logger = logging.getLogger("365advisers.super_alpha.factors.momentum")

_WEIGHTS = {
    "return_3m": 0.20,
    "return_6m": 0.30,
    "return_12m": 0.35,
    "ma_signal": 0.15,
}

# Population benchmarks (US equity market long-run averages)
_BENCHMARKS = {
    "return_3m": {"median": 0.025, "std": 0.10},    # ~2.5% ± 10%
    "return_6m": {"median": 0.05, "std": 0.15},     # ~5% ± 15%
    "return_12m": {"median": 0.10, "std": 0.20},    # ~10% ± 20%
    "ma_signal": {"median": 1.0, "std": 0.12},       # Price/SMA200 ~1.0 ± 12%
}


class MomentumFactor:
    """
    Produces a 0–100 Momentum Score from price return data.

    Usage::

        factor = MomentumFactor()
        score = factor.score({"return_3m": 0.12, "return_6m": 0.18,
                              "return_12m": 0.30, "price_to_sma200": 1.15})
    """

    def score(self, data: dict) -> FactorScore:
        """
        Compute momentum factor score.

        Parameters
        ----------
        data : dict
            Keys: return_3m, return_6m, return_12m (decimal returns),
                  price_to_sma200 (ratio, e.g. 1.10 means 10% above SMA200)
        """
        variables: list[VariableContribution] = []
        total_weighted_z = 0.0
        total_weight = 0.0
        available = 0

        # ── 3-Month Return ────────────────────────────────────────────────
        r3 = _f(data.get("return_3m"))
        if r3 is not None:
            z = _z(r3, "return_3m")
            w = _WEIGHTS["return_3m"]
            variables.append(VariableContribution(
                name="3M Return", raw_value=round(r3 * 100, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="3M Return", raw_value=None, weight=_WEIGHTS["return_3m"],
            ))

        # ── 6-Month Return ────────────────────────────────────────────────
        r6 = _f(data.get("return_6m"))
        if r6 is not None:
            z = _z(r6, "return_6m")
            w = _WEIGHTS["return_6m"]
            variables.append(VariableContribution(
                name="6M Return", raw_value=round(r6 * 100, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="6M Return", raw_value=None, weight=_WEIGHTS["return_6m"],
            ))

        # ── 12-Month Return ───────────────────────────────────────────────
        r12 = _f(data.get("return_12m"))
        if r12 is not None:
            z = _z(r12, "return_12m")
            w = _WEIGHTS["return_12m"]
            variables.append(VariableContribution(
                name="12M Return", raw_value=round(r12 * 100, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="12M Return", raw_value=None, weight=_WEIGHTS["return_12m"],
            ))

        # ── MA Signal (Price / SMA200) ────────────────────────────────────
        ma = _f(data.get("price_to_sma200"))
        if ma is not None:
            z = _z(ma, "ma_signal")
            w = _WEIGHTS["ma_signal"]
            variables.append(VariableContribution(
                name="Price/SMA200", raw_value=round(ma, 3),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="Price/SMA200", raw_value=None, weight=_WEIGHTS["ma_signal"],
            ))

        # ── Composite ─────────────────────────────────────────────────────
        data_quality = available / 4.0
        if total_weight > 0:
            composite_z = total_weighted_z / total_weight
            raw_score = _z_to_score(composite_z)
        else:
            raw_score = 50.0

        signals = self._generate_signals(data, raw_score)

        return FactorScore(
            factor=FactorName.MOMENTUM,
            score=round(raw_score, 1),
            variables=variables,
            signals=signals,
            data_quality=round(data_quality, 2),
        )

    def _generate_signals(self, data: dict, score: float) -> list[str]:
        signals = []
        r3 = _f(data.get("return_3m"))
        r12 = _f(data.get("return_12m"))
        ma = _f(data.get("price_to_sma200"))

        if score >= 80:
            signals.append("Strong multi-horizon momentum — trend confirmation across all periods")
        elif score >= 65:
            signals.append("Positive momentum — price trend intact")
        elif score <= 20:
            signals.append("Negative momentum — persistent downtrend across horizons")

        if r3 is not None and r12 is not None:
            if r3 > 0.15 and r12 > 0.25:
                signals.append("Accelerating returns — short-term outperforming long-term")
            elif r3 < -0.10 and r12 > 0.10:
                signals.append("Momentum reversal warning — recent pullback within uptrend")

        if ma is not None:
            if ma > 1.15:
                signals.append(f"Trading {(ma - 1) * 100:.0f}% above SMA200 — strong trend")
            elif ma < 0.90:
                signals.append(f"Trading {(1 - ma) * 100:.0f}% below SMA200 — downtrend")

        return signals[:5]


def _z(value: float, variable: str) -> float:
    bench = _BENCHMARKS[variable]
    std = bench["std"] if bench["std"] > 0 else 0.01
    return (value - bench["median"]) / std


def _z_to_score(z: float) -> float:
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2)))
    return min(max(cdf * 100.0, 0.0), 100.0)


def _f(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
