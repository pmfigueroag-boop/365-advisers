"""
src/engines/super_alpha/factors/quality.py
──────────────────────────────────────────────────────────────────────────────
Quality Factor Engine — measures business quality and profitability
durability using return-on-capital, margin stability, and leverage.

Variables: ROIC, Operating Margin, Earnings Stability, Leverage (inv)
Weights:   [0.30, 0.25, 0.25, 0.20]
Output:    0–100 Quality Score
"""

from __future__ import annotations

import logging
import math

from src.engines.super_alpha.models import (
    FactorName, FactorScore, VariableContribution,
)

logger = logging.getLogger("365advisers.super_alpha.factors.quality")

_WEIGHTS = {
    "roic": 0.30,
    "operating_margin": 0.25,
    "earnings_stability": 0.25,
    "leverage_inverse": 0.20,
}

# Population benchmarks (US large-cap)
_BENCHMARKS = {
    "roic": {"median": 0.12, "std": 0.08},           # ~12% ± 8%
    "operating_margin": {"median": 0.15, "std": 0.10}, # ~15% ± 10%
    "earnings_stability": {"median": 0.70, "std": 0.20}, # ~0.70 ± 0.20
    "leverage_inverse": {"median": 0.5, "std": 0.25},  # inv(D/E=2)=0.5 ± 0.25
}


class QualityFactor:
    """
    Produces a 0–100 Quality Score from profitability and balance sheet data.

    Usage::

        factor = QualityFactor()
        score = factor.score({
            "roic": 0.18, "operating_margin": 0.22,
            "earnings_stability": 0.85, "debt_to_equity": 0.8,
        })
    """

    def score(self, data: dict) -> FactorScore:
        """
        Compute quality factor score.

        Parameters
        ----------
        data : dict
            Keys: roic (decimal, e.g. 0.18 = 18%),
                  operating_margin (decimal),
                  earnings_stability (0–1, where 1 = perfectly stable EPS),
                  debt_to_equity (ratio, lower = better)
        """
        variables: list[VariableContribution] = []
        total_weighted_z = 0.0
        total_weight = 0.0
        available = 0

        # ── ROIC ──────────────────────────────────────────────────────────
        roic = _f(data.get("roic"))
        if roic is not None:
            z = _z(roic, "roic")
            w = _WEIGHTS["roic"]
            variables.append(VariableContribution(
                name="ROIC", raw_value=round(roic * 100, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="ROIC", raw_value=None, weight=_WEIGHTS["roic"],
            ))

        # ── Operating Margin ──────────────────────────────────────────────
        margin = _f(data.get("operating_margin"))
        if margin is not None:
            z = _z(margin, "operating_margin")
            w = _WEIGHTS["operating_margin"]
            variables.append(VariableContribution(
                name="Operating Margin", raw_value=round(margin * 100, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="Operating Margin", raw_value=None,
                weight=_WEIGHTS["operating_margin"],
            ))

        # ── Earnings Stability ────────────────────────────────────────────
        stability = _f(data.get("earnings_stability"))
        if stability is not None:
            stability = min(max(stability, 0), 1)
            z = _z(stability, "earnings_stability")
            w = _WEIGHTS["earnings_stability"]
            variables.append(VariableContribution(
                name="Earnings Stability", raw_value=round(stability, 3),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="Earnings Stability", raw_value=None,
                weight=_WEIGHTS["earnings_stability"],
            ))

        # ── Leverage (inverse of D/E — lower debt = higher quality) ──────
        de = _f(data.get("debt_to_equity"))
        if de is not None:
            lev_inv = 1.0 / max(de, 0.01)  # Avoid division by zero
            # Cap to reasonable range
            lev_inv = min(lev_inv, 5.0)
            z = _z(lev_inv, "leverage_inverse")
            w = _WEIGHTS["leverage_inverse"]
            variables.append(VariableContribution(
                name="Leverage (D/E)", raw_value=round(de, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="Leverage (D/E)", raw_value=None,
                weight=_WEIGHTS["leverage_inverse"],
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
            factor=FactorName.QUALITY,
            score=round(raw_score, 1),
            variables=variables,
            signals=signals,
            data_quality=round(data_quality, 2),
        )

    def _generate_signals(self, data: dict, score: float) -> list[str]:
        signals = []
        roic = _f(data.get("roic"))
        margin = _f(data.get("operating_margin"))
        stability = _f(data.get("earnings_stability"))
        de = _f(data.get("debt_to_equity"))

        if score >= 80:
            signals.append("Exceptional business quality — high returns, stable earnings, low leverage")
        elif score >= 65:
            signals.append("Above-average quality — solid fundamentals")
        elif score <= 20:
            signals.append("Low quality — weak margins, unstable earnings, or high leverage")

        if roic is not None and roic > 0.25:
            signals.append(f"Elite ROIC ({roic:.0%}) — strong competitive advantage")
        if roic is not None and roic < 0.05:
            signals.append(f"Low ROIC ({roic:.0%}) — poor capital deployment")

        if margin is not None and margin > 0.30:
            signals.append(f"High operating margin ({margin:.0%}) — pricing power")
        if stability is not None and stability > 0.90:
            signals.append("Highly predictable earnings stream")
        if de is not None and de > 3.0:
            signals.append(f"High leverage (D/E={de:.1f}x) — financial risk elevated")
        if de is not None and de < 0.3:
            signals.append("Conservative balance sheet — minimal debt")

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
