"""
src/engines/portfolio/position_sizing.py
──────────────────────────────────────────────────────────────────────────────
Position Sizing Model — determines target allocation % for a single position
based on opportunity score, risk conditions, and signal conviction.

Improvements over v1:
  1. Continuous scoring (linear interpolation, no discrete jumps)
  2. NORMAL risk = neutral (no penalty)
  3. Signal conviction override (strong signals boost allocation)
  4. Regime-aware allocation floors (minimum exposure for high conviction)
"""

from typing import TypedDict


class PositionAllocationResult(TypedDict):
    opportunity_score: float
    conviction_level: str
    risk_level: str
    base_position_size: float
    risk_adjustment: float
    conviction_boost: float
    suggested_allocation: float
    recommended_action: str


# ── Conviction Floors (minimum allocation even under adverse regimes) ────────

CONVICTION_FLOORS: dict[str, float] = {
    "Very High": 3.0,
    "High": 2.0,
    "Moderate": 1.0,
    "Watch": 0.5,
    "Avoid": 0.0,
}


class PositionSizingModel:

    @staticmethod
    def _continuous_base_size(score: float) -> float:
        """
        Linear interpolation for position sizing.

        Eliminates discrete bracket jumps:
          - score 9-10 → 8-10% (top picks, max conviction)
          - score 7-9  → 3-8%  (strong opportunities)
          - score 5-7  → 1-3%  (moderate, building position)
          - score <5   → 0%    (not investable)

        Example: score 6.79 → 1.0 + (6.79 - 5.0) * 1.0 = 2.79%
        """
        if score >= 9.0:
            return 8.0 + (score - 9.0) * 2.0      # 8-10%
        if score >= 7.0:
            return 3.0 + (score - 7.0) * 2.5       # 3-8%
        if score >= 5.0:
            return 1.0 + (score - 5.0) * 1.0       # 1-3%
        return 0.0

    @staticmethod
    def _conviction_from_score(score: float) -> str:
        """Map score to conviction label."""
        if score >= 9.0:
            return "Very High"
        if score >= 7.5:
            return "High"
        if score >= 6.0:
            return "Moderate"
        if score >= 5.0:
            return "Watch"
        return "Avoid"

    @staticmethod
    def _risk_multiplier(risk_condition: str) -> tuple[float, str]:
        """
        Risk adjustment — NORMAL is neutral (×1.00).

        Returns (multiplier, risk_level_label).
        """
        match risk_condition.upper():
            case "LOW":
                return 1.10, "Low"       # slight boost for calm markets
            case "NORMAL":
                return 1.00, "Medium"    # neutral — no penalty
            case "ELEVATED":
                return 0.75, "High"      # moderate reduction
            case "HIGH":
                return 0.50, "Extreme"   # significant reduction
            case _:
                return 1.00, "Medium"    # default = neutral

    @staticmethod
    def _signal_conviction_boost(
        strong_signal_ratio: float | None = None,
    ) -> float:
        """
        Boost allocation when signal conviction is overwhelming.

        If >80% of signals are STRONG, apply a multiplier:
          ratio 0.91 → boost = 1.0 + (0.91 - 0.80) * 1.5 = 1.165
        """
        if strong_signal_ratio is None or strong_signal_ratio <= 0.80:
            return 1.0
        return 1.0 + (strong_signal_ratio - 0.80) * 1.5

    @staticmethod
    def calculate(
        opportunity_score: float,
        risk_condition: str,
        strong_signal_ratio: float | None = None,
    ) -> PositionAllocationResult:
        """
        Calculates the suggested portfolio allocation.

        Parameters
        ----------
        opportunity_score : float
            Score 0-10 from the opportunity evaluation.
        risk_condition : str
            Volatility regime: "LOW", "NORMAL", "ELEVATED", "HIGH".
        strong_signal_ratio : float | None
            Ratio of signals that fired as STRONG (0.0-1.0).
            Used for conviction override when supplied.
        """
        model = PositionSizingModel

        # Step 1: Continuous base sizing
        base_size = model._continuous_base_size(opportunity_score)
        conviction = model._conviction_from_score(opportunity_score)

        # Step 2: Risk adjustment (NORMAL = neutral)
        risk_mult, risk_label = model._risk_multiplier(risk_condition)

        # Step 3: Signal conviction boost
        conv_boost = model._signal_conviction_boost(strong_signal_ratio)

        # Step 4: Combined calculation
        adj_size = base_size * risk_mult * conv_boost

        # Step 5: Apply floor (regime-aware minimum)
        floor = CONVICTION_FLOORS.get(conviction, 0.0)
        adj_size = max(adj_size, floor)

        # Step 6: Cap at single position limit
        final_size = min(adj_size, 10.0)

        # Step 7: Recommended action
        if final_size >= 6.0:
            action = "Increase Position"
        elif final_size >= 3.0:
            action = "Maintain Position"
        elif final_size > 0.0:
            action = "Build Position"
        else:
            action = "Exit Position"

        return {
            "opportunity_score": round(opportunity_score, 2),
            "conviction_level": conviction,
            "risk_level": risk_label,
            "base_position_size": round(base_size, 2),
            "risk_adjustment": round(risk_mult, 2),
            "conviction_boost": round(conv_boost, 2),
            "suggested_allocation": round(final_size, 2),
            "recommended_action": action,
        }
