"""
src/engines/super_alpha/factors/value.py
──────────────────────────────────────────────────────────────────────────────
Value Factor Engine — measures how cheap an asset is relative to its
fundamentals using cross-sectional z-score normalization.

Variables: P/E (inverse), EV/EBITDA (inverse), P/B (inverse), FCF Yield
Weights:   [0.30, 0.25, 0.20, 0.25]
Output:    0–100 Value Score
"""

from __future__ import annotations

import logging
import math

from src.engines.super_alpha.models import (
    FactorName, FactorScore, VariableContribution,
)

logger = logging.getLogger("365advisers.super_alpha.factors.value")

# Variable weights
_WEIGHTS = {
    "pe_inverse": 0.30,
    "ev_ebitda_inverse": 0.25,
    "pb_inverse": 0.20,
    "fcf_yield": 0.25,
}

# Scoring thresholds for single-asset mode (population stats approximation)
# These represent "typical" medians and std-devs for US large-cap equities.
_BENCHMARKS = {
    "pe_inverse": {"median": 1 / 20.0, "std": 1 / 15.0 - 1 / 25.0},   # ~0.05 ± 0.027
    "ev_ebitda_inverse": {"median": 1 / 14.0, "std": 1 / 10.0 - 1 / 18.0},
    "pb_inverse": {"median": 1 / 3.5, "std": 1 / 2.0 - 1 / 5.0},
    "fcf_yield": {"median": 0.04, "std": 0.025},
}


class ValueFactor:
    """
    Produces a 0–100 Value Score from company financial ratios.

    Usage::

        factor = ValueFactor()
        score = factor.score({"pe_ratio": 12, "ev_to_ebitda": 8, "pb_ratio": 1.5, "fcf_yield": 0.07})
    """

    def score(self, data: dict) -> FactorScore:
        """
        Compute value factor score.

        Parameters
        ----------
        data : dict
            Keys: pe_ratio, ev_to_ebitda, pb_ratio, fcf_yield
            All values should be positive floats. P/E, EV/EBITDA, P/B are
            raw ratios (lower = cheaper). FCF yield is already inverted
            (higher = cheaper).
        """
        variables: list[VariableContribution] = []
        total_weighted_z = 0.0
        total_weight = 0.0
        available = 0

        # ── P/E (inverse: lower P/E → higher value) ──────────────────────
        pe = _f(data.get("pe_ratio"))
        if pe is not None and pe > 0:
            pe_inv = 1.0 / pe
            z = self._z_score(pe_inv, "pe_inverse")
            w = _WEIGHTS["pe_inverse"]
            variables.append(VariableContribution(
                name="P/E Ratio", raw_value=round(pe, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="P/E Ratio", raw_value=None, weight=_WEIGHTS["pe_inverse"],
            ))

        # ── EV/EBITDA (inverse) ───────────────────────────────────────────
        ev = _f(data.get("ev_to_ebitda"))
        if ev is not None and ev > 0:
            ev_inv = 1.0 / ev
            z = self._z_score(ev_inv, "ev_ebitda_inverse")
            w = _WEIGHTS["ev_ebitda_inverse"]
            variables.append(VariableContribution(
                name="EV/EBITDA", raw_value=round(ev, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="EV/EBITDA", raw_value=None, weight=_WEIGHTS["ev_ebitda_inverse"],
            ))

        # ── P/B (inverse) ─────────────────────────────────────────────────
        pb = _f(data.get("pb_ratio"))
        if pb is not None and pb > 0:
            pb_inv = 1.0 / pb
            z = self._z_score(pb_inv, "pb_inverse")
            w = _WEIGHTS["pb_inverse"]
            variables.append(VariableContribution(
                name="P/B Ratio", raw_value=round(pb, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="P/B Ratio", raw_value=None, weight=_WEIGHTS["pb_inverse"],
            ))

        # ── FCF Yield (direct — higher = cheaper) ─────────────────────────
        fcf = _f(data.get("fcf_yield"))
        if fcf is not None:
            z = self._z_score(fcf, "fcf_yield")
            w = _WEIGHTS["fcf_yield"]
            variables.append(VariableContribution(
                name="FCF Yield", raw_value=round(fcf, 4),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="FCF Yield", raw_value=None, weight=_WEIGHTS["fcf_yield"],
            ))

        # ── Composite ─────────────────────────────────────────────────────
        data_quality = available / 4.0
        if total_weight > 0:
            composite_z = total_weighted_z / total_weight
            # Map z-score to 0–100 via normal CDF approximation
            raw_score = _z_to_score(composite_z)
        else:
            raw_score = 50.0

        # Generate signals
        signals = self._generate_signals(data, raw_score)

        return FactorScore(
            factor=FactorName.VALUE,
            score=round(raw_score, 1),
            variables=variables,
            signals=signals,
            data_quality=round(data_quality, 2),
        )

    def _z_score(self, value: float, variable: str) -> float:
        """Compute z-score vs population benchmark."""
        bench = _BENCHMARKS[variable]
        std = bench["std"] if bench["std"] > 0 else 0.01
        return (value - bench["median"]) / std

    def _generate_signals(self, data: dict, score: float) -> list[str]:
        signals = []
        pe = _f(data.get("pe_ratio"))
        ev = _f(data.get("ev_to_ebitda"))
        fcf = _f(data.get("fcf_yield"))

        if score >= 75:
            signals.append("Deep value — trading at significant discount to fundamentals")
        elif score >= 60:
            signals.append("Attractive valuation relative to peers")
        elif score <= 25:
            signals.append("Expensive valuation — limited margin of safety")

        if pe is not None and pe < 10:
            signals.append(f"Low P/E ({pe:.1f}x) — potential value trap or genuine bargain")
        if pe is not None and pe > 35:
            signals.append(f"Elevated P/E ({pe:.1f}x) — growth premium priced in")
        if fcf is not None and fcf > 0.08:
            signals.append(f"High FCF yield ({fcf:.1%}) — strong cash generation")
        if ev is not None and ev < 8:
            signals.append(f"Low EV/EBITDA ({ev:.1f}x) — asset-light value")

        return signals[:5]


def _z_to_score(z: float) -> float:
    """
    Map z-score to 0–100 using the normal CDF approximation.

    z = 0 → 50, z = +2 → ~97.7, z = -2 → ~2.3
    """
    # Abramowitz & Stegun approximation of Φ(z)
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2)))
    return min(max(cdf * 100.0, 0.0), 100.0)


def _f(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
