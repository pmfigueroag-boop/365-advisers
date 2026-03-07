"""
src/engines/portfolio_lab/comparison.py
─────────────────────────────────────────────────────────────────────────────
PortfolioComparison — side-by-side portfolio metrics comparison.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.portfolio_lab.comparison")


class PortfolioComparison:
    """Compare multiple portfolios side by side."""

    @staticmethod
    def compare(portfolios: list[dict]) -> dict:
        """Compare portfolio backtest results.

        Args:
            portfolios: List of {name, metrics, equity_curve, ...}

        Returns:
            Comparison table with rankings.
        """
        if not portfolios:
            return {"portfolios": [], "rankings": {}}

        # Extract key metrics
        rows = []
        for p in portfolios:
            m = p.get("metrics", {})
            rows.append({
                "name": p.get("strategy_name", p.get("name", "unnamed")),
                "total_return": m.get("total_return", 0),
                "annualized_return": m.get("annualized_return", 0),
                "sharpe_ratio": m.get("sharpe_ratio", 0),
                "sortino_ratio": m.get("sortino_ratio", 0),
                "max_drawdown": m.get("max_drawdown", 0),
                "calmar_ratio": m.get("calmar_ratio", 0),
                "win_rate": m.get("win_rate", 0),
                "alpha": m.get("alpha"),
                "information_ratio": m.get("information_ratio"),
                "volatility": m.get("annualized_volatility", 0),
                "total_cost": p.get("total_cost_usd", 0),
            })

        # Rankings
        rankings = {
            "best_return": _rank_by(rows, "total_return", reverse=True),
            "best_sharpe": _rank_by(rows, "sharpe_ratio", reverse=True),
            "lowest_drawdown": _rank_by(rows, "max_drawdown", reverse=False),
            "best_sortino": _rank_by(rows, "sortino_ratio", reverse=True),
            "lowest_cost": _rank_by(rows, "total_cost", reverse=False),
        }

        return {
            "portfolios": rows,
            "rankings": rankings,
            "count": len(rows),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def compute_efficient_frontier(portfolios: list[dict]) -> list[dict]:
        """Identify portfolios on the efficient frontier.

        A portfolio is efficient if no other portfolio has both
        higher return AND lower volatility.
        """
        points = []
        for p in portfolios:
            m = p.get("metrics", {})
            points.append({
                "name": p.get("strategy_name", p.get("name", "unnamed")),
                "return": m.get("annualized_return", 0),
                "volatility": m.get("annualized_volatility", 0),
                "sharpe": m.get("sharpe_ratio", 0),
            })

        # Sort by volatility ascending
        points.sort(key=lambda x: x["volatility"])

        # Find efficient frontier
        frontier = []
        max_return_so_far = float("-inf")

        for point in points:
            if point["return"] > max_return_so_far:
                frontier.append({**point, "on_frontier": True})
                max_return_so_far = point["return"]
            else:
                frontier.append({**point, "on_frontier": False})

        return frontier


def _rank_by(rows: list[dict], key: str, reverse: bool) -> list[str]:
    """Rank portfolios by a specific metric."""
    valid = [r for r in rows if r.get(key) is not None]
    sorted_rows = sorted(valid, key=lambda r: r[key], reverse=reverse)
    return [r["name"] for r in sorted_rows]
