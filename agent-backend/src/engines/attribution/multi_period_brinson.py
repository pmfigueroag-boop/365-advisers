"""
src/engines/attribution/multi_period_brinson.py
--------------------------------------------------------------------------
Multi-Period Brinson-Fachler Attribution with Geometric Linking.

Extends single-period Brinson to multi-period (monthly, quarterly, YTD)
using the Carino geometric linking method:

  Linked effect_i = effect_i × ln(1 + R_total) / R_total
                    × period_return_i / ln(1 + period_return_i)

This ensures single-period effects compound correctly to match the
total multi-period active return.

Usage::

    engine = MultiPeriodBrinson()
    result = engine.attribute_multi_period(periods)
"""

from __future__ import annotations

import logging
import math

from pydantic import BaseModel, Field

from src.engines.attribution.brinson import BrinsonFachler
from src.engines.attribution.models import BrinsonResult

logger = logging.getLogger("365advisers.attribution.multi_period")


# ── Contracts ────────────────────────────────────────────────────────────────

class PeriodData(BaseModel):
    """Input data for one attribution period."""
    period_label: str = ""
    portfolio_weights: dict[str, float] = Field(default_factory=dict)
    benchmark_weights: dict[str, float] = Field(default_factory=dict)
    portfolio_returns: dict[str, float] = Field(default_factory=dict)
    benchmark_returns: dict[str, float] = Field(default_factory=dict)


class LinkedAttribution(BaseModel):
    """Multi-period linked attribution result."""
    total_portfolio_return: float = 0.0
    total_benchmark_return: float = 0.0
    total_active_return: float = 0.0
    linked_allocation: float = 0.0
    linked_selection: float = 0.0
    linked_interaction: float = 0.0
    n_periods: int = 0
    period_results: list[BrinsonResult] = Field(default_factory=list)
    period_labels: list[str] = Field(default_factory=list)


# ── Engine ───────────────────────────────────────────────────────────────────

class MultiPeriodBrinson:
    """
    Multi-period Brinson-Fachler attribution with Carino linking.

    Compounding single-period effects using geometric linking ensures
    that linked effects sum to the total multi-period active return.
    """

    @classmethod
    def attribute_multi_period(
        cls,
        periods: list[PeriodData],
    ) -> LinkedAttribution:
        """
        Compute multi-period linked attribution.

        Parameters
        ----------
        periods : list[PeriodData]
            Ordered list of period data (e.g., monthly).
        """
        if not periods:
            return LinkedAttribution()

        # Step 1: Compute single-period results
        period_results: list[BrinsonResult] = []
        for pd in periods:
            result = BrinsonFachler.attribute(
                portfolio_weights=pd.portfolio_weights,
                benchmark_weights=pd.benchmark_weights,
                portfolio_returns=pd.portfolio_returns,
                benchmark_returns=pd.benchmark_returns,
            )
            period_results.append(result)

        # Step 2: Compound total returns
        cum_port = 1.0
        cum_bench = 1.0
        for r in period_results:
            cum_port *= (1 + r.portfolio_return)
            cum_bench *= (1 + r.benchmark_return)

        total_port = cum_port - 1
        total_bench = cum_bench - 1
        total_active = total_port - total_bench

        # Step 3: Carino geometric linking
        linked_alloc, linked_select, linked_interact = cls._carino_link(
            period_results, total_port,
        )

        return LinkedAttribution(
            total_portfolio_return=round(total_port, 6),
            total_benchmark_return=round(total_bench, 6),
            total_active_return=round(total_active, 6),
            linked_allocation=round(linked_alloc, 6),
            linked_selection=round(linked_select, 6),
            linked_interaction=round(linked_interact, 6),
            n_periods=len(periods),
            period_results=period_results,
            period_labels=[p.period_label for p in periods],
        )

    @classmethod
    def _carino_link(
        cls,
        period_results: list[BrinsonResult],
        total_return: float,
    ) -> tuple[float, float, float]:
        """
        Carino linking for multi-period attribution.

        Linking coefficient for each period:
          k_t = ln(1 + r_t) / r_t       (for the period)
          K   = ln(1 + R) / R           (for the total)
          linked_effect_t = effect_t × k_t / K
        """
        # Total linking coefficient
        if abs(total_return) < 1e-10:
            # Simple sum when total return ≈ 0
            alloc = sum(r.total_allocation for r in period_results)
            select = sum(r.total_selection for r in period_results)
            interact = sum(r.total_interaction for r in period_results)
            return alloc, select, interact

        K = math.log(1 + total_return) / total_return if abs(total_return) > 1e-10 else 1.0

        linked_alloc = 0.0
        linked_select = 0.0
        linked_interact = 0.0

        for r in period_results:
            r_t = r.portfolio_return
            # Period linking coefficient
            if abs(r_t) > 1e-10:
                k_t = math.log(1 + r_t) / r_t
            else:
                k_t = 1.0

            scale = k_t / K if abs(K) > 1e-10 else 1.0

            linked_alloc += r.total_allocation * scale
            linked_select += r.total_selection * scale
            linked_interact += r.total_interaction * scale

        return linked_alloc, linked_select, linked_interact
