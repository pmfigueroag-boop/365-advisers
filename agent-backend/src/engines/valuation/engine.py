"""
src/engines/valuation/engine.py
──────────────────────────────────────────────────────────────────────────────
Valuation Engine Orchestrator.

Aggregates DCF, Comparable Analysis, and Margin of Safety into a
unified valuation report.
"""

from __future__ import annotations

import logging
from typing import Any

from src.contracts.features import FundamentalFeatureSet
from src.engines.valuation.models import (
    DCFInput,
    DCFResult,
    ComparableInput,
    ComparableResult,
    PeerMultiple,
    MarginOfSafety,
    ValuationReport,
)
from src.engines.valuation.dcf import DCFModel
from src.engines.valuation.comparable import ComparableAnalysis
from src.engines.valuation.margin_of_safety import MarginCalculator

logger = logging.getLogger("365advisers.valuation.engine")


class ValuationEngine:
    """
    Orchestrates multi-method intrinsic valuation.

    Usage:
        engine = ValuationEngine()
        report = engine.full_valuation(
            ticker="AAPL",
            fundamental=features,
            current_price=175.0,
            peers=[PeerMultiple(...)],
        )
    """

    @classmethod
    def run_dcf(cls, inputs: DCFInput) -> DCFResult:
        """Run a standalone DCF valuation."""
        return DCFModel.calculate(inputs)

    @classmethod
    def run_comparable(cls, inputs: ComparableInput) -> ComparableResult:
        """Run a standalone comparable analysis."""
        return ComparableAnalysis.analyze(inputs)

    @classmethod
    def full_valuation(
        cls,
        ticker: str,
        current_price: float,
        fundamental: FundamentalFeatureSet | None = None,
        dcf_input: DCFInput | None = None,
        peers: list[PeerMultiple] | None = None,
        eps: float | None = None,
        book_value_per_share: float | None = None,
    ) -> ValuationReport:
        """
        Run a comprehensive valuation combining DCF + Comparable + Margin of Safety.

        If dcf_input is not provided, it attempts to derive DCF inputs from
        the FundamentalFeatureSet (using FCF yield × market cap as a proxy).

        Args:
            ticker: Stock ticker.
            current_price: Current market price.
            fundamental: Fundamental feature set (optional).
            dcf_input: Explicit DCF inputs (optional, takes priority).
            peers: List of peer multiples for comparable analysis.
            eps: Earnings per share (for Graham Number + PE comps).
            book_value_per_share: Book value per share (for Graham Number + PB comps).
        """
        dcf_result: DCFResult | None = None
        comp_result: ComparableResult | None = None

        # ── DCF ──────────────────────────────────────────────────────────
        if dcf_input:
            dcf_input.ticker = ticker
            dcf_result = DCFModel.calculate(dcf_input)
        elif fundamental:
            derived_input = cls._derive_dcf_inputs(ticker, fundamental, current_price)
            if derived_input:
                dcf_result = DCFModel.calculate(derived_input)

        # ── Comparable ───────────────────────────────────────────────────
        if peers:
            comp_input = ComparableInput(
                target_ticker=ticker,
                target_eps=eps or 0.0,
                target_ebitda=0.0,
                target_fcf_per_share=(
                    fundamental.fcf_yield * current_price if fundamental and fundamental.fcf_yield else 0.0
                ),
                target_book_value=book_value_per_share or 0.0,
                target_net_debt_per_share=0.0,
                peers=peers,
            )
            comp_result = ComparableAnalysis.analyze(comp_input)

        # ── Consensus Fair Value ─────────────────────────────────────────
        fair_values: list[tuple[float, float]] = []  # (value, weight)
        if dcf_result and dcf_result.fair_value_per_share > 0:
            fair_values.append((dcf_result.fair_value_per_share, 0.50))
        if comp_result and comp_result.consensus_fair_value > 0:
            fair_values.append((comp_result.consensus_fair_value, 0.50))

        if fair_values:
            total_weight = sum(w for _, w in fair_values)
            consensus = sum(v * w for v, w in fair_values) / total_weight
        else:
            consensus = 0.0

        # ── Margin of Safety ─────────────────────────────────────────────
        margin = MarginCalculator.calculate(
            ticker=ticker,
            fair_value=consensus,
            current_price=current_price,
            eps=eps,
            book_value_per_share=book_value_per_share,
        )

        # ── Upside ───────────────────────────────────────────────────────
        upside = ((consensus - current_price) / current_price * 100) if current_price > 0 and consensus > 0 else 0.0

        return ValuationReport(
            ticker=ticker,
            dcf=dcf_result,
            comparable=comp_result,
            margin_of_safety=margin,
            consensus_fair_value=round(consensus, 2),
            current_price=current_price,
            upside_pct=round(upside, 2),
        )

    @staticmethod
    def _derive_dcf_inputs(
        ticker: str,
        fundamental: FundamentalFeatureSet,
        current_price: float,
    ) -> DCFInput | None:
        """
        Attempt to derive DCF inputs from FundamentalFeatureSet.

        Uses:
            FCF = FCF_yield × market_cap (or FCF_yield × price as proxy)
            Growth = revenue_growth_yoy or earnings_growth_yoy
        """
        fcf_yield = fundamental.fcf_yield
        market_cap = fundamental.market_cap

        if not fcf_yield or not market_cap or market_cap <= 0:
            return None

        current_fcf = fcf_yield * market_cap  # in same units as market_cap
        if current_fcf <= 0:
            return None

        # Estimate shares outstanding from market cap / price
        shares = market_cap / max(current_price, 0.01)

        # Growth rate from fundamentals
        growth = fundamental.revenue_growth_yoy or fundamental.earnings_growth_yoy or 0.10
        growth = max(-0.20, min(growth, 0.50))  # cap to reasonable range

        # Estimate WACC from beta
        beta = fundamental.beta or 1.0
        risk_free = 0.04  # approx 10Y treasury
        equity_premium = 0.055
        wacc = risk_free + beta * equity_premium

        # Net debt proxy: D/E × market_cap
        de = fundamental.debt_to_equity or 0.0
        net_debt = de * market_cap * 0.3  # rough approximation

        return DCFInput(
            ticker=ticker,
            current_fcf=round(current_fcf, 2),
            growth_rate_stage1=round(growth, 4),
            growth_rate_stage2=round(growth * 0.5, 4),
            terminal_growth_rate=0.025,
            wacc=round(min(max(wacc, 0.05), 0.25), 4),
            stage1_years=5,
            stage2_years=3,
            shares_outstanding=round(shares, 2),
            net_debt=round(net_debt, 2),
        )
