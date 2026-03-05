"""
src/engines/portfolio/rebalancer.py
──────────────────────────────────────────────────────────────────────────────
Portfolio Rebalancer — generates rebalance actions by comparing current
portfolio state against target allocations.

Computes drift for each position and recommends BUY/SELL/HOLD actions
based on a configurable drift threshold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("365advisers.portfolio.rebalancer")


@dataclass
class RebalanceAction:
    """A single rebalance action for one position."""
    ticker: str
    current_weight: float
    target_weight: float
    drift: float              # target - current
    drift_pct: float          # abs(drift) / target  (0–1)
    action: str               # "BUY", "SELL", "HOLD", "EXIT", "NEW"


@dataclass
class RebalanceResult:
    """Complete rebalance recommendation."""
    actions: list[RebalanceAction] = field(default_factory=list)
    total_drift: float = 0.0     # Sum of absolute drifts
    needs_rebalance: bool = False
    summary: str = ""


class Rebalancer:
    """
    Compares current vs target portfolio and generates rebalance actions.

    Usage:
        result = Rebalancer(threshold=2.0).compute(current, target)
    """

    def __init__(self, threshold_pct: float = 2.0):
        """
        Args:
            threshold_pct: Minimum absolute drift (%) to trigger a rebalance action.
                           Below this, position is considered "HOLD".
        """
        self.threshold = threshold_pct

    def compute(
        self,
        current_positions: dict[str, float],
        target_positions: list[dict],
    ) -> RebalanceResult:
        """
        Generate rebalance actions.

        Args:
            current_positions: Dict of {ticker: current_weight_pct}.
            target_positions: List of dicts with "ticker" and "target_weight".

        Returns:
            RebalanceResult with per-position actions and summary.
        """
        result = RebalanceResult()
        all_tickers = set(current_positions.keys())
        target_map = {p["ticker"]: p["target_weight"] for p in target_positions}
        all_tickers.update(target_map.keys())

        for ticker in sorted(all_tickers):
            current = current_positions.get(ticker, 0.0)
            target = target_map.get(ticker, 0.0)
            drift = target - current
            drift_pct = abs(drift) / max(target, 0.01)  # avoid div by zero

            if target == 0.0 and current > 0.0:
                action = "EXIT"
            elif current == 0.0 and target > 0.0:
                action = "NEW"
            elif abs(drift) >= self.threshold:
                action = "BUY" if drift > 0 else "SELL"
            else:
                action = "HOLD"

            result.actions.append(RebalanceAction(
                ticker=ticker,
                current_weight=round(current, 2),
                target_weight=round(target, 2),
                drift=round(drift, 2),
                drift_pct=round(drift_pct, 4),
                action=action,
            ))

        result.total_drift = round(sum(abs(a.drift) for a in result.actions), 2)
        actionable = [a for a in result.actions if a.action != "HOLD"]
        result.needs_rebalance = len(actionable) > 0

        if result.needs_rebalance:
            buys = sum(1 for a in actionable if a.action in ("BUY", "NEW"))
            sells = sum(1 for a in actionable if a.action in ("SELL", "EXIT"))
            result.summary = (
                f"Rebalance needed: {buys} buy(s), {sells} sell(s). "
                f"Total drift: {result.total_drift}%"
            )
        else:
            result.summary = f"Portfolio aligned. Total drift: {result.total_drift}%"

        return result
