"""
src/engines/attribution/brinson.py — Brinson-Fachler attribution model.

Decomposes active return into:
  Allocation effect:  Σ (w_p,s - w_b,s) × (r_b,s - r_b)
  Selection effect:   Σ w_b,s × (r_p,s - r_b,s)
  Interaction effect: Σ (w_p,s - w_b,s) × (r_p,s - r_b,s)
"""
from __future__ import annotations
import logging
from src.engines.attribution.models import SectorAttribution, BrinsonResult

logger = logging.getLogger("365advisers.attribution.brinson")


class BrinsonFachler:
    """Brinson-Fachler single-period attribution."""

    @classmethod
    def attribute(
        cls,
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_returns: dict[str, float],
    ) -> BrinsonResult:
        """
        Args:
            portfolio_weights: sector → weight in portfolio
            benchmark_weights: sector → weight in benchmark
            portfolio_returns: sector → return in portfolio
            benchmark_returns: sector → return in benchmark
        """
        all_sectors = sorted(set(portfolio_weights.keys()) | set(benchmark_weights.keys()))

        # Total benchmark return
        r_b = sum(benchmark_weights.get(s, 0) * benchmark_returns.get(s, 0) for s in all_sectors)

        sector_attrs = []
        total_alloc = 0.0
        total_select = 0.0
        total_interaction = 0.0

        for sector in all_sectors:
            w_p = portfolio_weights.get(sector, 0)
            w_b = benchmark_weights.get(sector, 0)
            r_p_s = portfolio_returns.get(sector, 0)
            r_b_s = benchmark_returns.get(sector, 0)

            # Brinson-Fachler formulas
            allocation = (w_p - w_b) * (r_b_s - r_b)
            selection = w_b * (r_p_s - r_b_s)
            interaction = (w_p - w_b) * (r_p_s - r_b_s)
            total = allocation + selection + interaction

            sector_attrs.append(SectorAttribution(
                sector=sector,
                portfolio_weight=round(w_p, 6),
                benchmark_weight=round(w_b, 6),
                portfolio_return=round(r_p_s, 6),
                benchmark_return=round(r_b_s, 6),
                allocation_effect=round(allocation, 6),
                selection_effect=round(selection, 6),
                interaction_effect=round(interaction, 6),
                total_effect=round(total, 6),
            ))

            total_alloc += allocation
            total_select += selection
            total_interaction += interaction

        # Portfolio return
        r_p = sum(portfolio_weights.get(s, 0) * portfolio_returns.get(s, 0) for s in all_sectors)

        # Top contributors / detractors
        sorted_sectors = sorted(sector_attrs, key=lambda s: s.total_effect, reverse=True)
        top_pos = [s.sector for s in sorted_sectors[:3] if s.total_effect > 0]
        top_neg = [s.sector for s in sorted_sectors[-3:] if s.total_effect < 0]

        return BrinsonResult(
            portfolio_return=round(r_p, 6),
            benchmark_return=round(r_b, 6),
            active_return=round(r_p - r_b, 6),
            total_allocation=round(total_alloc, 6),
            total_selection=round(total_select, 6),
            total_interaction=round(total_interaction, 6),
            sector_attribution=sector_attrs,
            top_contributors=top_pos,
            top_detractors=top_neg,
        )
