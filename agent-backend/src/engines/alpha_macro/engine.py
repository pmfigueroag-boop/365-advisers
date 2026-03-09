"""
src/engines/alpha_macro/engine.py
──────────────────────────────────────────────────────────────────────────────
Alpha Macro Engine — detects macroeconomic regimes and generates
allocation signals from FRED, World Bank, and IMF data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_macro.models import (
    MacroRegime, MacroScore, MacroIndicatorReading,
    AssetAllocationSuggestion, MacroDashboard,
)

logger = logging.getLogger("365advisers.alpha_macro.engine")

# ── Regime-based allocation templates ─────────────────────────────────────────
_ALLOCATION_TEMPLATES: dict[MacroRegime, dict] = {
    MacroRegime.EXPANSION: {"equities_tilt": 0.6, "bonds_tilt": -0.2, "commodities_tilt": 0.3, "cash_tilt": -0.3, "rationale": "Pro-growth: overweight equities & commodities, underweight bonds & cash"},
    MacroRegime.SLOWDOWN: {"equities_tilt": 0.0, "bonds_tilt": 0.3, "commodities_tilt": -0.2, "cash_tilt": 0.2, "rationale": "Defensive rotation: shift to bonds, raise cash, reduce commodity exposure"},
    MacroRegime.RECESSION: {"equities_tilt": -0.5, "bonds_tilt": 0.5, "commodities_tilt": -0.4, "cash_tilt": 0.5, "rationale": "Risk-off: overweight bonds & cash, underweight equities & commodities"},
    MacroRegime.RECOVERY: {"equities_tilt": 0.4, "bonds_tilt": 0.0, "commodities_tilt": 0.2, "cash_tilt": -0.2, "rationale": "Early-cycle: re-enter equities & commodities, reduce cash"},
}


class AlphaMacroEngine:
    """
    Detects macro regime from economic indicator readings and produces
    allocation signals.

    Usage::

        engine = AlphaMacroEngine()
        dashboard = engine.analyze(indicators)
    """

    def analyze(self, indicators: dict) -> MacroDashboard:
        """
        Run macro analysis.

        Parameters
        ----------
        indicators : dict
            Keys: gdp_growth, inflation, unemployment, interest_rate,
                  yield_curve_spread, pmi, consumer_confidence, etc.
        """
        readings = self._build_readings(indicators)
        regime, confidence, probs = self._detect_regime(indicators)
        score = self._compute_score(regime, readings)

        macro_score = MacroScore(
            regime=regime,
            regime_confidence=confidence,
            regime_probabilities=probs,
            composite_score=score,
            indicators=readings,
            signals=self._generate_signals(regime, readings),
            evaluated_at=datetime.now(timezone.utc),
        )

        alloc_template = _ALLOCATION_TEMPLATES[regime]
        allocation = AssetAllocationSuggestion(regime=regime, **alloc_template)
        risks = self._identify_risks(indicators, regime)

        return MacroDashboard(score=macro_score, allocation=allocation, key_risks=risks)

    def _detect_regime(self, ind: dict) -> tuple[MacroRegime, float, dict]:
        """Simple rule-based regime detection."""
        gdp = _f(ind.get("gdp_growth"))
        unemp = _f(ind.get("unemployment"))
        yc = _f(ind.get("yield_curve_spread"))
        infl = _f(ind.get("inflation"))
        pmi = _f(ind.get("pmi"))

        # Score each regime's likelihood (0–1)
        expansion_score = 0.0
        slowdown_score = 0.0
        recession_score = 0.0
        recovery_score = 0.0

        if gdp is not None:
            if gdp > 3.0: expansion_score += 0.3
            elif gdp > 1.5: expansion_score += 0.15; recovery_score += 0.1
            elif gdp > 0: slowdown_score += 0.2; recovery_score += 0.15
            else: recession_score += 0.35

        if unemp is not None:
            if unemp < 4.0: expansion_score += 0.2
            elif unemp < 5.5: expansion_score += 0.1; recovery_score += 0.1
            elif unemp < 7.0: slowdown_score += 0.2
            else: recession_score += 0.25

        if yc is not None:
            if yc < -0.2: recession_score += 0.25  # inverted yield curve
            elif yc < 0.5: slowdown_score += 0.15
            else: expansion_score += 0.15

        if pmi is not None:
            if pmi > 55: expansion_score += 0.2
            elif pmi > 50: expansion_score += 0.1; recovery_score += 0.1
            elif pmi > 45: slowdown_score += 0.2
            else: recession_score += 0.2

        if infl is not None:
            if infl > 6.0: slowdown_score += 0.15  # stagflation risk
            elif infl > 3.5: slowdown_score += 0.05

        total = max(expansion_score + slowdown_score + recession_score + recovery_score, 0.01)
        probs = {
            "expansion": round(expansion_score / total, 3),
            "slowdown": round(slowdown_score / total, 3),
            "recession": round(recession_score / total, 3),
            "recovery": round(recovery_score / total, 3),
        }

        regime_map = {
            "expansion": MacroRegime.EXPANSION,
            "slowdown": MacroRegime.SLOWDOWN,
            "recession": MacroRegime.RECESSION,
            "recovery": MacroRegime.RECOVERY,
        }
        best_key = max(probs, key=lambda k: probs[k])
        return regime_map[best_key], probs[best_key], probs

    def _build_readings(self, ind: dict) -> list[MacroIndicatorReading]:
        readings = []
        mapping = {
            "gdp_growth": "GDP Growth",
            "inflation": "Inflation (CPI)",
            "unemployment": "Unemployment Rate",
            "interest_rate": "Fed Funds Rate",
            "yield_curve_spread": "Yield Curve (10Y-2Y)",
            "pmi": "PMI Manufacturing",
            "consumer_confidence": "Consumer Confidence",
        }
        for key, name in mapping.items():
            val = _f(ind.get(key))
            if val is not None:
                signal = "neutral"
                if key == "gdp_growth":
                    signal = "bullish" if val > 2.0 else "bearish" if val < 0 else "neutral"
                elif key == "unemployment":
                    signal = "bullish" if val < 4.5 else "bearish" if val > 6.0 else "neutral"
                elif key == "yield_curve_spread":
                    signal = "bearish" if val < 0 else "bullish" if val > 1.0 else "neutral"
                elif key == "pmi":
                    signal = "bullish" if val > 52 else "bearish" if val < 48 else "neutral"
                readings.append(MacroIndicatorReading(name=name, value=val, signal=signal))
        return readings

    def _compute_score(self, regime: MacroRegime, readings: list) -> float:
        base = {"expansion": 75, "slowdown": 45, "recession": 20, "recovery": 60}
        score = base.get(regime.value, 50)
        bullish_count = sum(1 for r in readings if r.signal == "bullish")
        bearish_count = sum(1 for r in readings if r.signal == "bearish")
        adjustment = (bullish_count - bearish_count) * 3
        return min(max(score + adjustment, 0), 100)

    def _generate_signals(self, regime: MacroRegime, readings: list) -> list[str]:
        signals = [f"Regime: {regime.value.upper()}"]
        for r in readings:
            if r.signal != "neutral":
                signals.append(f"{r.name}: {r.signal} ({r.value})")
        return signals

    def _identify_risks(self, ind: dict, regime: MacroRegime) -> list[str]:
        risks = []
        infl = _f(ind.get("inflation"))
        yc = _f(ind.get("yield_curve_spread"))
        unemp = _f(ind.get("unemployment"))
        if infl and infl > 5.0: risks.append(f"Inflation elevated at {infl}%")
        if yc and yc < 0: risks.append("Inverted yield curve — recession signal")
        if unemp and unemp > 6.0: risks.append(f"High unemployment: {unemp}%")
        if regime == MacroRegime.RECESSION: risks.append("Economy in contraction")
        return risks


def _f(val) -> float | None:
    if val is None: return None
    try: return float(val)
    except (ValueError, TypeError): return None
