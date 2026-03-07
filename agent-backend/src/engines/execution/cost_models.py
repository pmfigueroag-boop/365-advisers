"""
src/engines/execution/slippage_model.py
─────────────────────────────────────────────────────────────────────────────
SlippageModel — size-dependent price slippage estimation.

Models the relationship between order size, average daily volume,
and expected price slippage for realistic backtest cost simulation.
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger("365advisers.execution.slippage")


class SlippageModel:
    """Estimate price slippage based on order size and liquidity."""

    def __init__(
        self,
        base_slippage_bps: float = 2.0,
        size_impact_exponent: float = 0.6,
        urgency_multipliers: dict[str, float] | None = None,
    ):
        self.base_slippage_bps = base_slippage_bps
        self.size_impact_exponent = size_impact_exponent
        self.urgency_multipliers = urgency_multipliers or {
            "passive": 0.3,
            "normal": 1.0,
            "aggressive": 2.5,
        }

    def estimate(
        self,
        order_value_usd: float,
        adv_usd: float,
        urgency: str = "normal",
    ) -> dict:
        """Estimate slippage for an order.

        Args:
            order_value_usd: Order notional value
            adv_usd: Average daily volume in USD
            urgency: "passive" | "normal" | "aggressive"

        Returns:
            {slippage_bps, slippage_usd, participation_rate, liquidity_tier}
        """
        if adv_usd <= 0:
            return {"slippage_bps": 0.0, "error": "Invalid ADV"}

        participation = order_value_usd / adv_usd
        urgency_factor = self.urgency_multipliers.get(urgency, 1.0)

        # Slippage = base × (participation)^exponent × urgency
        slippage_bps = (
            self.base_slippage_bps
            * (participation * 100) ** self.size_impact_exponent
            * urgency_factor
        )
        slippage_bps = max(0.5, min(slippage_bps, 100.0))

        slippage_usd = order_value_usd * slippage_bps / 10_000
        tier = _classify_liquidity(adv_usd)

        return {
            "slippage_bps": round(slippage_bps, 2),
            "slippage_usd": round(slippage_usd, 2),
            "participation_rate": round(participation, 6),
            "urgency": urgency,
            "liquidity_tier": tier,
        }


class SpreadModel:
    """Estimate bid-ask spread cost by liquidity tier."""

    TIER_SPREADS = {
        "mega_cap": 0.5,
        "large_cap": 1.5,
        "mid_cap": 4.0,
        "small_cap": 10.0,
        "micro_cap": 25.0,
    }

    def estimate(self, adv_usd: float, spread_bps: float | None = None) -> dict:
        """Estimate half-spread cost.

        If explicit spread not provided, estimates from liquidity tier.
        """
        tier = _classify_liquidity(adv_usd)

        if spread_bps is None:
            spread_bps = self.TIER_SPREADS.get(tier, 5.0)

        half_spread = spread_bps / 2.0

        return {
            "spread_bps": round(spread_bps, 2),
            "half_spread_bps": round(half_spread, 2),
            "liquidity_tier": tier,
        }


class MarketImpactModel:
    """Almgren-Chriss inspired temporary + permanent market impact model."""

    def __init__(
        self,
        temporary_impact_coeff: float = 0.1,
        permanent_impact_coeff: float = 0.05,
        volatility_default: float = 0.02,
    ):
        self.temp_coeff = temporary_impact_coeff
        self.perm_coeff = permanent_impact_coeff
        self.vol_default = volatility_default

    def estimate(
        self,
        order_value_usd: float,
        adv_usd: float,
        daily_volatility: float | None = None,
    ) -> dict:
        """Estimate market impact using Almgren-Chriss framework.

        Args:
            order_value_usd: Order notional
            adv_usd: Average daily volume
            daily_volatility: Daily return volatility (default 2%)

        Returns:
            {temporary_impact_bps, permanent_impact_bps, total_impact_bps}
        """
        if adv_usd <= 0:
            return {"total_impact_bps": 0.0, "error": "Invalid ADV"}

        vol = daily_volatility or self.vol_default
        participation = order_value_usd / adv_usd

        # Temporary impact: η × σ × (Q/V)^0.5
        temp_impact = self.temp_coeff * vol * math.sqrt(participation) * 10_000

        # Permanent impact: γ × σ × (Q/V)
        perm_impact = self.perm_coeff * vol * participation * 10_000

        total = temp_impact + perm_impact

        return {
            "temporary_impact_bps": round(temp_impact, 2),
            "permanent_impact_bps": round(perm_impact, 2),
            "total_impact_bps": round(total, 2),
            "participation_rate": round(participation, 6),
            "volatility_used": round(vol, 4),
        }


class ExecutionCostAggregator:
    """Aggregate all execution costs into a single estimate."""

    def __init__(
        self,
        commission_bps: float = 1.0,
        slippage_model: SlippageModel | None = None,
        spread_model: SpreadModel | None = None,
        impact_model: MarketImpactModel | None = None,
    ):
        self.commission_bps = commission_bps
        self.slippage = slippage_model or SlippageModel()
        self.spread = spread_model or SpreadModel()
        self.impact = impact_model or MarketImpactModel()

    def estimate_total_cost(
        self,
        order_value_usd: float,
        adv_usd: float,
        urgency: str = "normal",
        daily_volatility: float | None = None,
        explicit_spread_bps: float | None = None,
    ) -> dict:
        """Estimate total execution cost for a trade.

        Returns:
            Full cost breakdown: commission + spread + slippage + impact
        """
        slip = self.slippage.estimate(order_value_usd, adv_usd, urgency)
        spr = self.spread.estimate(adv_usd, explicit_spread_bps)
        imp = self.impact.estimate(order_value_usd, adv_usd, daily_volatility)

        total_bps = (
            self.commission_bps
            + spr.get("half_spread_bps", 0)
            + slip.get("slippage_bps", 0)
            + imp.get("total_impact_bps", 0)
        )

        total_usd = order_value_usd * total_bps / 10_000

        return {
            "commission_bps": self.commission_bps,
            "half_spread_bps": spr.get("half_spread_bps", 0),
            "slippage_bps": slip.get("slippage_bps", 0),
            "market_impact_bps": imp.get("total_impact_bps", 0),
            "total_cost_bps": round(total_bps, 2),
            "total_cost_usd": round(total_usd, 2),
            "order_value_usd": order_value_usd,
            "participation_rate": slip.get("participation_rate", 0),
            "liquidity_tier": slip.get("liquidity_tier", "unknown"),
            "urgency": urgency,
        }


def _classify_liquidity(adv_usd: float) -> str:
    """Classify liquidity tier from average daily volume."""
    if adv_usd >= 500_000_000:
        return "mega_cap"
    elif adv_usd >= 50_000_000:
        return "large_cap"
    elif adv_usd >= 10_000_000:
        return "mid_cap"
    elif adv_usd >= 1_000_000:
        return "small_cap"
    else:
        return "micro_cap"
