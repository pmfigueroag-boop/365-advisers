"""
src/engines/portfolio_lab/attribution.py
─────────────────────────────────────────────────────────────────────────────
AttributionEngine — decompose portfolio returns by source.

Brinson-style attribution:
  - Allocation effect (sector/category over/underweighting)
  - Selection effect (stock picking within sectors)
  - Interaction effect
"""

from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger("365advisers.portfolio_lab.attribution")


class AttributionEngine:
    """Brinson-style portfolio return attribution."""

    @staticmethod
    def attribute(
        portfolio_positions: list[dict],
        benchmark_positions: list[dict],
        portfolio_return: float,
        benchmark_return: float,
    ) -> dict:
        """Decompose active return into allocation + selection + interaction.

        Args:
            portfolio_positions: [{ticker, weight, return, sector}]
            benchmark_positions: [{ticker, weight, return, sector}]
            portfolio_return: Total portfolio return
            benchmark_return: Total benchmark return

        Returns:
            Attribution breakdown by sector and total.
        """
        active_return = portfolio_return - benchmark_return

        # Group by sector
        port_sectors = _group_by_sector(portfolio_positions)
        bench_sectors = _group_by_sector(benchmark_positions)
        all_sectors = sorted(set(list(port_sectors.keys()) + list(bench_sectors.keys())))

        sector_attribution = {}
        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        for sector in all_sectors:
            p = port_sectors.get(sector, {"weight": 0.0, "return": 0.0})
            b = bench_sectors.get(sector, {"weight": 0.0, "return": 0.0})

            # Allocation effect: (wp - wb) × (Rb - R_total_benchmark)
            allocation = (p["weight"] - b["weight"]) * (b["return"] - benchmark_return)

            # Selection effect: wb × (Rp - Rb)
            selection = b["weight"] * (p["return"] - b["return"])

            # Interaction: (wp - wb) × (Rp - Rb)
            interaction = (p["weight"] - b["weight"]) * (p["return"] - b["return"])

            sector_attribution[sector] = {
                "portfolio_weight": round(p["weight"], 4),
                "benchmark_weight": round(b["weight"], 4),
                "portfolio_return": round(p["return"], 4),
                "benchmark_return": round(b["return"], 4),
                "allocation_effect": round(allocation, 6),
                "selection_effect": round(selection, 6),
                "interaction_effect": round(interaction, 6),
                "total_contribution": round(allocation + selection + interaction, 6),
            }

            total_allocation += allocation
            total_selection += selection
            total_interaction += interaction

        return {
            "active_return": round(active_return, 4),
            "allocation_effect": round(total_allocation, 4),
            "selection_effect": round(total_selection, 4),
            "interaction_effect": round(total_interaction, 4),
            "explained_active": round(total_allocation + total_selection + total_interaction, 4),
            "residual": round(active_return - (total_allocation + total_selection + total_interaction), 6),
            "sector_attribution": sector_attribution,
        }

    @staticmethod
    def attribute_by_signal(
        positions: list[dict],
        signal_contributions: dict[str, dict[str, float]],
    ) -> dict:
        """Attribute returns by signal source.

        Args:
            positions: [{ticker, weight, return}]
            signal_contributions: {ticker: {signal_id: contribution_score}}

        Returns:
            Return attribution by signal.
        """
        signal_returns: dict[str, float] = defaultdict(float)
        signal_weights: dict[str, float] = defaultdict(float)

        for pos in positions:
            ticker = pos["ticker"]
            pos_return = pos.get("return", 0.0)
            weight = pos.get("weight", 0.0)
            contribs = signal_contributions.get(ticker, {})

            if contribs:
                total_contrib = sum(contribs.values())
                for signal_id, contrib in contribs.items():
                    frac = contrib / total_contrib if total_contrib > 0 else 0
                    signal_returns[signal_id] += weight * pos_return * frac
                    signal_weights[signal_id] += weight * frac

        result = {}
        for signal_id in signal_returns:
            result[signal_id] = {
                "attributed_return": round(signal_returns[signal_id], 6),
                "effective_weight": round(signal_weights[signal_id], 4),
            }

        return {"signal_attribution": result}


def _group_by_sector(positions: list[dict]) -> dict[str, dict]:
    """Group positions by sector and compute weighted returns."""
    sectors: dict[str, dict[str, float]] = defaultdict(lambda: {"weight": 0.0, "wt_return": 0.0})

    for pos in positions:
        sector = pos.get("sector", "Other")
        w = pos.get("weight", 0.0)
        r = pos.get("return", 0.0)
        sectors[sector]["weight"] += w
        sectors[sector]["wt_return"] += w * r

    result = {}
    for sector, data in sectors.items():
        w = data["weight"]
        result[sector] = {
            "weight": w,
            "return": data["wt_return"] / w if w > 0 else 0.0,
        }

    return result
