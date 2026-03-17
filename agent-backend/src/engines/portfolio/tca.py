"""
src/engines/portfolio/tca.py
--------------------------------------------------------------------------
Transaction Cost Analysis (TCA) — measures execution quality.

Institutional-grade TCA goes beyond cost estimation to measure how well
you actually executed:

  - Implementation Shortfall (IS): gap between decision price and average fill
  - VWAP benchmark: were fills better or worse than VWAP?
  - Slippage tracking: estimated vs actual costs
  - Fill quality: % filled at limit, market impact realized

This module provides the framework. In production, connect to execution
management system (EMS) fill data.

Usage::

    tca = TCAEngine()
    tca.record_fill(fill)
    report = tca.analyze(start_date, end_date)
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from collections import defaultdict

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.portfolio.tca")


# ── Contracts ────────────────────────────────────────────────────────────────

class OrderFill(BaseModel):
    """A single execution fill."""
    order_id: str
    ticker: str
    side: str = ""         # "BUY" or "SELL"
    decision_price: float  # Price when decision was made
    fill_price: float      # Actual average fill price
    shares: int = 0
    fill_value: float = 0.0
    vwap: float = 0.0      # VWAP benchmark for the period
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    fill_date: date = Field(default_factory=date.today)


class FillAnalysis(BaseModel):
    """Analysis of a single fill."""
    order_id: str
    ticker: str
    side: str = ""

    # Implementation Shortfall components
    implementation_shortfall_bps: float = 0.0
    realized_impact_bps: float = 0.0
    delay_cost_bps: float = 0.0

    # VWAP comparison
    vs_vwap_bps: float = 0.0
    beat_vwap: bool = False

    # Fill quality
    fill_value: float = 0.0
    slippage_dollars: float = 0.0


class TCAReport(BaseModel):
    """Aggregate TCA report."""
    period_start: date | None = None
    period_end: date | None = None
    total_fills: int = 0
    total_volume: float = 0.0

    # Aggregate metrics
    avg_implementation_shortfall_bps: float = 0.0
    avg_vs_vwap_bps: float = 0.0
    pct_beat_vwap: float = 0.0

    # Slippage
    total_slippage_dollars: float = 0.0
    avg_slippage_bps: float = 0.0

    # Distribution
    worst_fill_bps: float = 0.0
    best_fill_bps: float = 0.0

    # By ticker
    slippage_by_ticker: dict[str, float] = Field(default_factory=dict)

    # Fill-level details
    fill_analyses: list[FillAnalysis] = Field(default_factory=list)


# ── Engine ───────────────────────────────────────────────────────────────────

class TCAEngine:
    """
    Transaction Cost Analysis engine.

    Records execution fills and analyzes execution quality against
    benchmarks (decision price, VWAP).

    Implementation Shortfall (IS)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IS = (Fill Price - Decision Price) / Decision Price
    For buys: positive IS = you paid more than expected (bad)
    For sells: negative IS = you received less than expected (bad)

    VWAP Benchmark
    ~~~~~~~~~~~~~~
    vs_VWAP = (Fill Price - VWAP) / VWAP
    For buys: negative = beat VWAP (good)
    For sells: positive = beat VWAP (good)
    """

    def __init__(self) -> None:
        self._fills: list[OrderFill] = []

    def record_fill(self, fill: OrderFill) -> FillAnalysis:
        """Record a fill and compute immediate analysis."""
        self._fills.append(fill)
        analysis = self._analyze_fill(fill)

        logger.info(
            "TCA: %s %s %d shares @ %.2f (decision=%.2f, IS=%.1fbps, "
            "vs_VWAP=%.1fbps)",
            fill.side, fill.ticker, fill.shares,
            fill.fill_price, fill.decision_price,
            analysis.implementation_shortfall_bps,
            analysis.vs_vwap_bps,
        )

        return analysis

    def record_fills(self, fills: list[OrderFill]) -> list[FillAnalysis]:
        """Record multiple fills."""
        return [self.record_fill(f) for f in fills]

    def analyze(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        ticker: str | None = None,
    ) -> TCAReport:
        """
        Generate aggregate TCA report for a period.

        Parameters
        ----------
        start_date : date | None
            Filter: fills on or after this date.
        end_date : date | None
            Filter: fills on or before this date.
        ticker : str | None
            Filter: specific ticker only.
        """
        fills = self._fills

        if start_date:
            fills = [f for f in fills if f.fill_date >= start_date]
        if end_date:
            fills = [f for f in fills if f.fill_date <= end_date]
        if ticker:
            fills = [f for f in fills if f.ticker == ticker]

        if not fills:
            return TCAReport(
                period_start=start_date,
                period_end=end_date,
            )

        analyses = [self._analyze_fill(f) for f in fills]

        # Aggregate
        n = len(analyses)
        total_volume = sum(a.fill_value for a in analyses)
        total_slippage = sum(a.slippage_dollars for a in analyses)

        # Volume-weighted averages
        is_values = [a.implementation_shortfall_bps for a in analyses]
        vwap_values = [a.vs_vwap_bps for a in analyses]

        weights = [a.fill_value for a in analyses]
        total_w = sum(weights) or 1.0

        avg_is = sum(v * w for v, w in zip(is_values, weights)) / total_w
        avg_vwap = sum(v * w for v, w in zip(vwap_values, weights)) / total_w
        avg_slip = (total_slippage / total_volume * 10_000) if total_volume > 0 else 0.0

        pct_beat = sum(1 for a in analyses if a.beat_vwap) / n * 100

        # By ticker
        slip_by_ticker: dict[str, float] = defaultdict(float)
        for a in analyses:
            slip_by_ticker[a.ticker] += a.slippage_dollars

        return TCAReport(
            period_start=start_date or min(f.fill_date for f in fills),
            period_end=end_date or max(f.fill_date for f in fills),
            total_fills=n,
            total_volume=round(total_volume, 2),
            avg_implementation_shortfall_bps=round(avg_is, 2),
            avg_vs_vwap_bps=round(avg_vwap, 2),
            pct_beat_vwap=round(pct_beat, 1),
            total_slippage_dollars=round(total_slippage, 2),
            avg_slippage_bps=round(avg_slip, 2),
            worst_fill_bps=round(max(is_values), 2),
            best_fill_bps=round(min(is_values), 2),
            slippage_by_ticker=dict(slip_by_ticker),
            fill_analyses=analyses,
        )

    def _analyze_fill(self, fill: OrderFill) -> FillAnalysis:
        """Analyze a single fill."""
        dp = fill.decision_price
        fp = fill.fill_price

        if dp <= 0:
            return FillAnalysis(order_id=fill.order_id, ticker=fill.ticker)

        # Implementation Shortfall
        is_raw = (fp - dp) / dp
        if fill.side == "SELL":
            is_raw = -is_raw  # For sells, getting less = positive IS (bad)

        is_bps = is_raw * 10_000

        # VWAP comparison
        vs_vwap_bps = 0.0
        beat_vwap = False
        if fill.vwap > 0:
            vwap_raw = (fp - fill.vwap) / fill.vwap
            if fill.side == "SELL":
                vwap_raw = -vwap_raw
            vs_vwap_bps = vwap_raw * 10_000
            beat_vwap = vs_vwap_bps < 0  # Lower IS = better

        # Slippage in dollars
        slippage = abs(fp - dp) * fill.shares
        fill_value = fp * fill.shares

        return FillAnalysis(
            order_id=fill.order_id,
            ticker=fill.ticker,
            side=fill.side,
            implementation_shortfall_bps=round(is_bps, 2),
            realized_impact_bps=round(abs(is_bps), 2),
            vs_vwap_bps=round(vs_vwap_bps, 2),
            beat_vwap=beat_vwap,
            fill_value=round(fill_value, 2),
            slippage_dollars=round(slippage, 2),
        )

    @property
    def fill_count(self) -> int:
        return len(self._fills)

    def clear(self) -> None:
        """Clear all recorded fills."""
        self._fills.clear()
