"""
src/engines/alpha_volatility/engine.py
──────────────────────────────────────────────────────────────────────────────
Alpha Volatility Engine — analyses VIX, implied volatility, skew,
and term structure to produce regime classification and risk signals.

Data Sources: Cboe, options data (via EDPL)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_volatility.models import (
    VolRegime, VolScore, VolSignal, VolDashboard,
)

logger = logging.getLogger("365advisers.alpha_volatility.engine")


class AlphaVolatilityEngine:
    """
    Produces volatility risk scores, regime classification, and
    actionable signals.

    Usage::

        engine = AlphaVolatilityEngine()
        dashboard = engine.analyze(vol_data)
    """

    def analyze(self, data: dict) -> VolDashboard:
        """
        Run volatility analysis.

        Parameters
        ----------
        data : dict
            Keys: vix_current, vix_high, vix_low, vix_1yr_avg, vix_1yr_max,
                  iv_rank, realized_vol, iv_current, term_structure_slope,
                  put_call_skew, put_call_ratio
        """
        vix = _f(data.get("vix_current"))
        regime = self._classify_regime(vix)
        score = self._compute_score(data, regime)
        signals = self._generate_signals(data, regime)
        risk_indicators = self._build_risk_indicators(data)

        return VolDashboard(score=score, signals=signals, risk_indicators=risk_indicators)

    def _classify_regime(self, vix: float | None) -> VolRegime:
        if vix is None: return VolRegime.NORMAL
        if vix < 15: return VolRegime.LOW
        if vix < 20: return VolRegime.NORMAL
        if vix < 30: return VolRegime.ELEVATED
        return VolRegime.EXTREME

    def _compute_score(self, data: dict, regime: VolRegime) -> VolScore:
        vix = _f(data.get("vix_current"))
        iv_rank = _f(data.get("iv_rank"))
        rv = _f(data.get("realized_vol"))
        iv = _f(data.get("iv_current"))
        slope = _f(data.get("term_structure_slope"))
        skew = _f(data.get("put_call_skew"))
        vix_avg = _f(data.get("vix_1yr_avg"))
        vix_max = _f(data.get("vix_1yr_max"))

        # VIX percentile (vs 1yr range)
        vix_pct = None
        if vix is not None and vix_avg is not None and vix_max is not None:
            vix_range = max(vix_max - 10, 1)  # floor at 10
            vix_pct = min(max((vix - 10) / vix_range * 100, 0), 100)

        # IV-RV spread
        iv_rv = None
        if iv is not None and rv is not None:
            iv_rv = round(iv - rv, 2)

        # Term structure classification
        term = "normal"
        if slope is not None:
            if slope < -0.5: term = "backwardation"
            elif slope < 0.3: term = "flat"
            else: term = "contango"

        # Composite risk: 0=ultra calm, 100=crisis
        risk = 50.0
        if vix is not None:
            risk = min(max((vix - 10) * 3.3, 0), 100)
        if iv_rank is not None:
            risk = risk * 0.6 + iv_rank * 0.4
        if term == "backwardation":
            risk = min(risk + 10, 100)

        signals = []
        if regime == VolRegime.EXTREME: signals.append("⚠ Extreme volatility regime (VIX > 30)")
        if term == "backwardation": signals.append("Term structure inverted — stress signal")
        if iv_rv is not None and iv_rv > 10: signals.append(f"IV premium over RV: {iv_rv:.1f} pts")
        if iv_rank is not None and iv_rank > 80: signals.append(f"IV Rank elevated: {iv_rank:.0f}")

        return VolScore(
            composite_risk=round(risk, 1), regime=regime,
            vix_level=vix, vix_percentile=round(vix_pct, 1) if vix_pct else None,
            iv_rank=iv_rank, iv_rv_spread=iv_rv,
            term_structure=term, skew_z=skew, signals=signals,
        )

    def _generate_signals(self, data: dict, regime: VolRegime) -> list[VolSignal]:
        signals = []
        vix = _f(data.get("vix_current"))
        iv_rank = _f(data.get("iv_rank"))
        pcr = _f(data.get("put_call_ratio"))
        slope = _f(data.get("term_structure_slope"))

        if regime in (VolRegime.ELEVATED, VolRegime.EXTREME):
            signals.append(VolSignal(
                signal_type="regime_shift", description=f"VIX at {vix:.1f} — {regime.value} regime",
                severity="high" if regime == VolRegime.EXTREME else "moderate",
            ))
        if iv_rank is not None and iv_rank > 85:
            signals.append(VolSignal(
                signal_type="iv_spike", description=f"IV Rank at {iv_rank:.0f}th percentile",
                severity="high",
            ))
        if slope is not None and slope < -0.5:
            signals.append(VolSignal(
                signal_type="skew_warning", description="Term structure inversion — near-term stress",
                severity="high",
            ))
        if pcr is not None and pcr > 1.5:
            signals.append(VolSignal(
                signal_type="uoa", description=f"Put/Call ratio elevated: {pcr:.2f}",
                severity="moderate",
            ))
        return signals

    def _build_risk_indicators(self, data: dict) -> dict[str, float]:
        indicators = {}
        for key in ["vix_current", "iv_rank", "realized_vol", "put_call_ratio"]:
            val = _f(data.get(key))
            if val is not None:
                indicators[key] = round(val, 2)
        return indicators


def _f(val) -> float | None:
    if val is None: return None
    try: return float(val)
    except (ValueError, TypeError): return None
