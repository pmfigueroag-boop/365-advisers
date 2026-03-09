"""
src/engines/super_alpha/factors/size.py
──────────────────────────────────────────────────────────────────────────────
Size Factor Engine — evaluates market capitalisation and liquidity
characteristics. The Fama-French size factor (SMB) captures the
empirical small-cap premium.

Variables: ln(Market Cap) inverse, Liquidity, Small-Cap Premium
Weights:   [0.50, 0.30, 0.20]
Output:    0–100 Size Exposure Score
"""

from __future__ import annotations

import logging
import math

from src.engines.super_alpha.models import (
    FactorName, FactorScore, VariableContribution,
)

logger = logging.getLogger("365advisers.super_alpha.factors.size")

_WEIGHTS = {
    "ln_mcap_inverse": 0.50,
    "liquidity": 0.30,
    "small_cap_premium": 0.20,
}

# Thresholds
_SMALL_CAP_THRESHOLD = 2e9      # $2B
_MID_CAP_THRESHOLD = 10e9       # $10B
_LARGE_CAP_THRESHOLD = 100e9    # $100B

# Benchmarks for z-score (based on US equity universe)
_BENCHMARKS = {
    "ln_mcap_inverse": {"median": -math.log(20e9), "std": 1.5},
    "liquidity": {"median": 5e6, "std": 10e6},  # avg daily volume in USD
}


class SizeFactor:
    """
    Produces a 0–100 Size Exposure Score.

    Higher score → more small-cap exposure (captures SMB premium).
    Lower score → large-cap characteristics.

    Usage::

        factor = SizeFactor()
        score = factor.score({
            "market_cap": 1.5e9,
            "avg_daily_volume_usd": 3e6,
        })
    """

    def score(self, data: dict) -> FactorScore:
        """
        Compute size factor score.

        Parameters
        ----------
        data : dict
            Keys: market_cap (USD), avg_daily_volume_usd (USD)
        """
        variables: list[VariableContribution] = []
        total_weighted_z = 0.0
        total_weight = 0.0
        available = 0

        mcap = _f(data.get("market_cap"))
        adv = _f(data.get("avg_daily_volume_usd"))

        # ── Market Cap (inverse log — smaller = higher score) ─────────────
        if mcap is not None and mcap > 0:
            ln_inv = -math.log(mcap)
            bench = _BENCHMARKS["ln_mcap_inverse"]
            z = (ln_inv - bench["median"]) / max(bench["std"], 0.01)
            w = _WEIGHTS["ln_mcap_inverse"]
            variables.append(VariableContribution(
                name="Market Cap", raw_value=round(mcap / 1e9, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="Market Cap", raw_value=None, weight=_WEIGHTS["ln_mcap_inverse"],
            ))

        # ── Liquidity ─────────────────────────────────────────────────────
        if adv is not None and adv > 0:
            bench = _BENCHMARKS["liquidity"]
            z = (adv - bench["median"]) / max(bench["std"], 1)
            z = max(min(z, 3.0), -3.0)  # Cap to prevent extreme ADV dominating
            w = _WEIGHTS["liquidity"]
            variables.append(VariableContribution(
                name="Avg Daily Volume", raw_value=round(adv / 1e6, 2),
                z_score=round(z, 3), weight=w,
                weighted_contribution=round(z * w, 3),
            ))
            total_weighted_z += z * w
            total_weight += w
            available += 1
        else:
            variables.append(VariableContribution(
                name="Avg Daily Volume", raw_value=None,
                weight=_WEIGHTS["liquidity"],
            ))

        # ── Small-Cap Premium (binary tilt) ───────────────────────────────
        premium_z = 0.0
        if mcap is not None:
            if mcap < _SMALL_CAP_THRESHOLD:
                premium_z = 1.5    # Strong positive tilt
            elif mcap < _MID_CAP_THRESHOLD:
                premium_z = 0.5    # Moderate positive tilt
            else:
                premium_z = -0.5   # Large cap — negative tilt

        w = _WEIGHTS["small_cap_premium"]
        cap_label = self._classify_cap(mcap) if mcap else "Unknown"
        variables.append(VariableContribution(
            name="Small Cap Premium", raw_value=premium_z,
            z_score=round(premium_z, 3), weight=w,
            weighted_contribution=round(premium_z * w, 3),
        ))
        total_weighted_z += premium_z * w
        total_weight += w
        if mcap is not None:
            available += 1

        # ── Composite ─────────────────────────────────────────────────────
        data_quality = available / 3.0
        if total_weight > 0:
            composite_z = total_weighted_z / total_weight
            raw_score = _z_to_score(composite_z)
        else:
            raw_score = 50.0

        signals = self._generate_signals(mcap, adv, raw_score)

        return FactorScore(
            factor=FactorName.SIZE,
            score=round(raw_score, 1),
            variables=variables,
            signals=signals,
            data_quality=round(data_quality, 2),
        )

    def _classify_cap(self, mcap: float | None) -> str:
        if mcap is None:
            return "Unknown"
        if mcap < _SMALL_CAP_THRESHOLD:
            return "Small Cap"
        if mcap < _MID_CAP_THRESHOLD:
            return "Mid Cap"
        if mcap < _LARGE_CAP_THRESHOLD:
            return "Large Cap"
        return "Mega Cap"

    def _generate_signals(
        self, mcap: float | None, adv: float | None, score: float
    ) -> list[str]:
        signals = []
        cap_label = self._classify_cap(mcap)

        if cap_label != "Unknown":
            signals.append(f"{cap_label} classification")

        if score >= 70:
            signals.append("Small-cap premium exposure — historically higher returns, higher vol")
        elif score <= 30:
            signals.append("Large-cap profile — stability and institutional ownership")

        if mcap is not None and mcap < _SMALL_CAP_THRESHOLD:
            signals.append("Qualifies for small-cap premium factor (< $2B market cap)")
        if adv is not None and adv < 1e6:
            signals.append("Low liquidity — wider spreads and higher execution costs")
        if adv is not None and adv > 50e6:
            signals.append("Highly liquid — minimal market impact")

        return signals[:5]


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
