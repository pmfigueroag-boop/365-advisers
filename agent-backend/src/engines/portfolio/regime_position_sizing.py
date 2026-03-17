"""
src/engines/portfolio/regime_position_sizing.py
--------------------------------------------------------------------------
Regime-Aware Position Sizing — scales portfolio weights based on the
current market regime.

Logic:
  - High volatility → scale down (×0.5-0.7)
  - Low vol + trending → scale up (×1.1-1.3)
  - Mean reverting → reduce directional bets
  - Crisis → maximum de-risk (×0.3)

Integrates with:
  - RebalancingEngine: adjusts target weights before transition
  - Regime detection: uses vol regime and trend regime

Usage::

    sizer = RegimePositionSizer()
    adjusted = sizer.adjust(
        weights={"AAPL": 0.20, "MSFT": 0.30},
        volatility_regime="high",
        trend_regime="trending",
    )
"""

from __future__ import annotations

import logging
import math

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.portfolio.regime_sizing")


# ── Contracts ────────────────────────────────────────────────────────────────

class RegimeSizingConfig(BaseModel):
    """Configuration for regime-aware sizing."""
    # Volatility regime multipliers
    crisis_multiplier: float = Field(0.30, description="Crisis: max de-risk")
    high_vol_multiplier: float = Field(0.60, description="High vol: reduce")
    normal_vol_multiplier: float = Field(1.00, description="Normal: no change")
    low_vol_multiplier: float = Field(1.15, description="Low vol: slight leverage")

    # Trend regime adjustments
    trending_bonus: float = Field(0.10, description="Trending: +10% on trend dir")
    mean_reverting_penalty: float = Field(
        -0.10, description="Mean reverting: -10% on directional bets",
    )
    choppy_penalty: float = Field(-0.05, description="Choppy: -5%")

    # Safety
    max_total_exposure: float = Field(
        1.0, description="Never exceed 100% exposure",
    )
    cash_floor: float = Field(
        0.05, description="Always keep at least 5% cash",
    )


class RegimeContext(BaseModel):
    """Current market regime."""
    volatility_regime: str = "normal"  # "crisis", "high", "normal", "low"
    trend_regime: str = "neutral"      # "trending", "mean_reverting", "choppy", "neutral"
    vix_level: float = 0.0
    realized_vol_percentile: float = 50.0  # Percentile rank (0-100)


class SizingResult(BaseModel):
    """Result of regime-aware sizing."""
    original_weights: dict[str, float] = Field(default_factory=dict)
    adjusted_weights: dict[str, float] = Field(default_factory=dict)
    regime: RegimeContext = Field(default_factory=RegimeContext)
    vol_multiplier: float = 1.0
    trend_adjustment: float = 0.0
    total_exposure: float = 0.0
    cash_allocation: float = 0.0
    scaling_applied: str = ""


# ── Engine ───────────────────────────────────────────────────────────────────

class RegimePositionSizer:
    """
    Adjusts position sizes based on market regime.

    Process:
    1. Determine vol multiplier from volatility regime
    2. Apply trend adjustment
    3. Scale all weights × combined multiplier
    4. Enforce max exposure and cash floor
    5. Re-normalize
    """

    def __init__(self, config: RegimeSizingConfig | None = None) -> None:
        self.config = config or RegimeSizingConfig()

    def adjust(
        self,
        weights: dict[str, float],
        regime: RegimeContext | None = None,
        volatility_regime: str = "normal",
        trend_regime: str = "neutral",
    ) -> SizingResult:
        """
        Adjust portfolio weights for current regime.

        Parameters
        ----------
        weights : dict[str, float]
            Original target weights.
        regime : RegimeContext | None
            Full regime context, or use simple strings below.
        volatility_regime : str
            "crisis", "high", "normal", "low".
        trend_regime : str
            "trending", "mean_reverting", "choppy", "neutral".
        """
        if regime is None:
            regime = RegimeContext(
                volatility_regime=volatility_regime,
                trend_regime=trend_regime,
            )

        # Step 1: Vol multiplier
        vol_mult = self._vol_multiplier(regime.volatility_regime)

        # Step 2: Trend adjustment
        trend_adj = self._trend_adjustment(regime.trend_regime)

        # Step 3: Combined multiplier
        combined = vol_mult + trend_adj
        combined = max(combined, 0.1)  # Never go below 10%

        # Step 4: Scale weights
        adjusted = {t: w * combined for t, w in weights.items()}

        # Step 5: Enforce max exposure
        total_exposure = sum(adjusted.values())
        max_exposure = self.config.max_total_exposure - self.config.cash_floor

        if total_exposure > max_exposure:
            scale = max_exposure / total_exposure
            adjusted = {t: w * scale for t, w in adjusted.items()}
            total_exposure = sum(adjusted.values())

        # Round
        adjusted = {t: round(w, 6) for t, w in adjusted.items() if w > 0.001}
        cash = max(1.0 - sum(adjusted.values()), 0)

        scaling_desc = (
            f"{regime.volatility_regime} vol (×{vol_mult:.2f}) + "
            f"{regime.trend_regime} trend ({trend_adj:+.2f}) "
            f"= ×{combined:.2f}"
        )

        logger.info(
            "REGIME-SIZING: %s → exposure=%.1f%%, cash=%.1f%%",
            scaling_desc, total_exposure * 100, cash * 100,
        )

        return SizingResult(
            original_weights=weights,
            adjusted_weights=adjusted,
            regime=regime,
            vol_multiplier=round(vol_mult, 4),
            trend_adjustment=round(trend_adj, 4),
            total_exposure=round(total_exposure, 4),
            cash_allocation=round(cash, 4),
            scaling_applied=scaling_desc,
        )

    def classify_regime(
        self,
        realized_vol: float,
        vol_percentile: float = 50.0,
        trend_strength: float = 0.0,
    ) -> RegimeContext:
        """
        Classify current market regime from metrics.

        Parameters
        ----------
        realized_vol : float
            Current annualized realized volatility.
        vol_percentile : float
            Percentile rank of current vol vs history (0-100).
        trend_strength : float
            Trend strength (-1 = strong down, 0 = none, +1 = strong up).
        """
        # Volatility regime
        if vol_percentile >= 95:
            vol_regime = "crisis"
        elif vol_percentile >= 75:
            vol_regime = "high"
        elif vol_percentile <= 25:
            vol_regime = "low"
        else:
            vol_regime = "normal"

        # Trend regime
        if abs(trend_strength) >= 0.5:
            trend_regime = "trending"
        elif abs(trend_strength) <= 0.15:
            trend_regime = "choppy"
        else:
            trend_regime = "neutral"

        return RegimeContext(
            volatility_regime=vol_regime,
            trend_regime=trend_regime,
            realized_vol_percentile=vol_percentile,
        )

    def _vol_multiplier(self, vol_regime: str) -> float:
        match vol_regime:
            case "crisis":
                return self.config.crisis_multiplier
            case "high":
                return self.config.high_vol_multiplier
            case "low":
                return self.config.low_vol_multiplier
            case _:
                return self.config.normal_vol_multiplier

    def _trend_adjustment(self, trend_regime: str) -> float:
        match trend_regime:
            case "trending":
                return self.config.trending_bonus
            case "mean_reverting":
                return self.config.mean_reverting_penalty
            case "choppy":
                return self.config.choppy_penalty
            case _:
                return 0.0
