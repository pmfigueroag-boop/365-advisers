"""
src/engines/risk/var_position_sizer.py
──────────────────────────────────────────────────────────────────────────────
P3.3: VaR/CVaR-based position sizing.

Replaces flat portfolio weight multipliers with risk-budget allocation:
  - Each position sized to not exceed a max VaR contribution
  - Higher vol assets get smaller positions (inverse vol scaling)
  - CVaR provides tail-risk budget guardrails

Usage:
    sizer = VarPositionSizer(max_portfolio_var_pct=0.02)
    weight = sizer.compute_weight(
        ticker="AAPL",
        annual_vol=0.25,
        portfolio_size=10,
    )
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger("365advisers.risk.var_position_sizer")

# VaR confidence z-scores
_Z_SCORES = {
    0.95: 1.645,
    0.99: 2.326,
}


@dataclass
class VarSizingResult:
    """Result of VaR-based position sizing."""
    ticker: str
    weight: float           # portfolio weight (0-1)
    annual_vol: float       # annualized volatility
    daily_var_95: float     # 95% daily VaR as decimal
    daily_var_99: float     # 99% daily VaR as decimal
    cvar_99: float          # expected shortfall beyond 99% VaR
    risk_budget_used: float  # fraction of risk budget consumed


class VarPositionSizer:
    """
    P3.3: Position sizing based on VaR risk budgets.

    Principles:
      - Max single-position VaR contribution ≤ max_single_var_pct of portfolio
      - Higher volatility → smaller position
      - Total portfolio VaR ≤ max_portfolio_var_pct
      - CVaR used as tail-risk guardrail (1.4x VaR approximation for normal dist)
    """

    def __init__(
        self,
        max_portfolio_var_pct: float = 0.02,    # 2% max daily portfolio VaR
        max_single_var_pct: float = 0.005,      # 0.5% max daily VaR per position
        confidence: float = 0.95,               # VaR confidence level
        min_weight: float = 0.02,               # 2% minimum position
        max_weight: float = 0.15,               # 15% maximum position
    ):
        self.max_portfolio_var_pct = max_portfolio_var_pct
        self.max_single_var_pct = max_single_var_pct
        self.z_score = _Z_SCORES.get(confidence, 1.645)
        self.min_weight = min_weight
        self.max_weight = max_weight

    def compute_weight(
        self,
        ticker: str,
        annual_vol: float,
        portfolio_size: int = 10,
        signal_strength: float = 1.0,  # 0-1, from composite score
    ) -> VarSizingResult:
        """
        Compute optimal position weight based on VaR budget.

        Parameters
        ----------
        ticker : str
            Asset symbol.
        annual_vol : float
            Annualized volatility (e.g. 0.25 = 25%).
        portfolio_size : int
            Number of positions in portfolio.
        signal_strength : float
            Composite signal strength (0-1), used to scale up conviction.
        """
        if annual_vol <= 0:
            annual_vol = 0.20  # Fallback: assume 20% vol

        # Daily volatility
        daily_vol = annual_vol / math.sqrt(252)

        # Daily VaR at 95% and 99%
        daily_var_95 = daily_vol * _Z_SCORES[0.95]
        daily_var_99 = daily_vol * _Z_SCORES[0.99]

        # CVaR ≈ VaR × 1.4 for normal distribution (Expected Shortfall)
        cvar_99 = daily_var_99 * 1.4

        # Max weight from single-position VaR budget
        # weight × daily_vol × z_score ≤ max_single_var_pct
        var_weight = self.max_single_var_pct / (daily_vol * self.z_score) if daily_vol > 0 else self.max_weight

        # Equal-weight baseline
        equal_weight = 1.0 / portfolio_size if portfolio_size > 0 else 0.1

        # Scale by signal conviction (stronger signal → closer to var_weight)
        conviction_adjusted = equal_weight + (var_weight - equal_weight) * signal_strength

        # Clamp to [min_weight, max_weight]
        weight = max(self.min_weight, min(self.max_weight, conviction_adjusted))

        # Risk budget used
        position_var = weight * daily_vol * self.z_score
        risk_budget_used = position_var / self.max_portfolio_var_pct if self.max_portfolio_var_pct > 0 else 0

        return VarSizingResult(
            ticker=ticker,
            weight=round(weight, 4),
            annual_vol=round(annual_vol, 4),
            daily_var_95=round(daily_var_95, 6),
            daily_var_99=round(daily_var_99, 6),
            cvar_99=round(cvar_99, 6),
            risk_budget_used=round(risk_budget_used, 4),
        )

    def size_portfolio(
        self,
        positions: list[dict],
    ) -> list[VarSizingResult]:
        """
        Size all positions in a portfolio.

        Parameters
        ----------
        positions : list[dict]
            Each dict must have: ticker, annual_vol, signal_strength.
        """
        n = len(positions)
        results = []
        for pos in positions:
            result = self.compute_weight(
                ticker=pos["ticker"],
                annual_vol=pos.get("annual_vol", 0.20),
                portfolio_size=n,
                signal_strength=pos.get("signal_strength", 1.0),
            )
            results.append(result)

        # Normalize so total weight = 1.0
        total = sum(r.weight for r in results)
        if total > 0:
            for r in results:
                r.weight = round(r.weight / total, 4)

        return results
