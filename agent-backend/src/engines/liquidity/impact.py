"""
src/engines/liquidity/impact.py
─────────────────────────────────────────────────────────────────────────────
MarketImpactModel — Simplified Almgren-Chriss market impact estimation.
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger("365advisers.liquidity.impact")


class MarketImpactModel:
    """Almgren-Chriss simplified market impact model.

    impact(bps) = permanent_impact + temporary_impact
    permanent = gamma × sigma × (Q/V)^0.5
    temporary = eta × sigma × (Q/(V×tau))^0.6

    Where:
      Q = order shares, V = ADV, sigma = daily volatility,
      tau = execution time (days), gamma/eta = model params
    """

    def __init__(
        self,
        gamma: float = 0.314,   # Permanent impact scaling
        eta: float = 0.142,     # Temporary impact scaling
    ) -> None:
        self.gamma = gamma
        self.eta = eta

    def estimate_impact(
        self,
        order_shares: int,
        adv: float,
        daily_volatility: float,
        price: float,
        execution_days: float = 1.0,
    ) -> dict:
        """Estimate market impact for an order.

        Args:
            order_shares: Number of shares to execute.
            adv: Average daily volume.
            daily_volatility: Daily return volatility (e.g., 0.02 = 2%).
            price: Current stock price.
            execution_days: Time to execute the order in days.

        Returns:
            Dict with permanent, temporary, total impact in bps and $.
        """
        if adv <= 0 or price <= 0:
            return {"error": "Invalid ADV or price"}

        participation = order_shares / adv

        # Permanent impact
        permanent_pct = self.gamma * daily_volatility * math.sqrt(participation)

        # Temporary impact
        tempo_ratio = order_shares / (adv * execution_days) if execution_days > 0 else participation
        temporary_pct = self.eta * daily_volatility * (tempo_ratio ** 0.6)

        total_pct = permanent_pct + temporary_pct
        total_bps = total_pct * 10000
        total_usd = total_pct * price * order_shares

        return {
            "order_shares": order_shares,
            "participation_rate": round(participation, 6),
            "permanent_impact_bps": round(permanent_pct * 10000, 2),
            "temporary_impact_bps": round(temporary_pct * 10000, 2),
            "total_impact_bps": round(total_bps, 2),
            "total_impact_usd": round(total_usd, 2),
            "execution_days": execution_days,
        }

    def compute_optimal_execution_time(
        self,
        order_shares: int,
        adv: float,
        daily_volatility: float,
        risk_aversion: float = 1.0,
    ) -> float:
        """Estimate optimal execution horizon (in days).

        Balances market impact (shorter = more impact) against
        timing risk (longer = more price drift).
        """
        if adv <= 0:
            return 1.0

        participation = order_shares / adv

        # Heuristic: optimal_tau ≈ sqrt(participation / risk_aversion) × scaling
        optimal = math.sqrt(participation / max(risk_aversion, 0.01)) * 5

        # Clamp to [0.1, 10] days
        return max(0.1, min(optimal, 10.0))
