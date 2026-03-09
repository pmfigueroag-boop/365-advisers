"""
tests/test_valuation.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Intrinsic Valuation Engine.
"""

import math

import pytest

from src.engines.valuation.models import (
    DCFInput,
    DCFResult,
    CashFlowProjection,
    SensitivityCell,
    ComparableInput,
    ComparableResult,
    PeerMultiple,
    MarginOfSafety,
    ValuationVerdict,
    ValuationReport,
)
from src.engines.valuation.dcf import DCFModel
from src.engines.valuation.comparable import ComparableAnalysis
from src.engines.valuation.margin_of_safety import MarginCalculator
from src.engines.valuation.engine import ValuationEngine
from src.contracts.features import FundamentalFeatureSet


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_dcf_input(**overrides) -> DCFInput:
    defaults = dict(
        ticker="AAPL",
        current_fcf=100_000.0,  # $100B FCF (in $M)
        growth_rate_stage1=0.10,
        growth_rate_stage2=0.05,
        terminal_growth_rate=0.025,
        wacc=0.10,
        stage1_years=5,
        stage2_years=3,
        shares_outstanding=15_000.0,  # 15B shares
        net_debt=50_000.0,
    )
    defaults.update(overrides)
    return DCFInput(**defaults)


def _make_peers() -> list[PeerMultiple]:
    return [
        PeerMultiple(ticker="MSFT", pe_ratio=30.0, ev_ebitda=22.0, p_fcf=28.0, pb_ratio=12.0),
        PeerMultiple(ticker="GOOGL", pe_ratio=25.0, ev_ebitda=18.0, p_fcf=24.0, pb_ratio=6.0),
        PeerMultiple(ticker="META", pe_ratio=22.0, ev_ebitda=15.0, p_fcf=20.0, pb_ratio=7.0),
        PeerMultiple(ticker="AMZN", pe_ratio=35.0, ev_ebitda=25.0, p_fcf=32.0, pb_ratio=8.0),
    ]


# ── DCF Tests ────────────────────────────────────────────────────────────────

class TestDCFModel:
    def test_basic_dcf(self):
        inputs = _make_dcf_input()
        result = DCFModel.calculate(inputs)
        assert isinstance(result, DCFResult)
        assert result.fair_value_per_share > 0
        assert result.enterprise_value > 0
        assert result.equity_value > 0
        assert len(result.projections) == 8  # 5 stage1 + 3 stage2

    def test_projection_stages(self):
        result = DCFModel.calculate(_make_dcf_input())
        stage1 = [p for p in result.projections if p.stage == "stage1"]
        stage2 = [p for p in result.projections if p.stage == "stage2"]
        assert len(stage1) == 5
        assert len(stage2) == 3

    def test_higher_growth_higher_value(self):
        low = DCFModel.calculate(_make_dcf_input(growth_rate_stage1=0.05))
        high = DCFModel.calculate(_make_dcf_input(growth_rate_stage1=0.20))
        assert high.fair_value_per_share > low.fair_value_per_share

    def test_higher_wacc_lower_value(self):
        low_wacc = DCFModel.calculate(_make_dcf_input(wacc=0.08))
        high_wacc = DCFModel.calculate(_make_dcf_input(wacc=0.15))
        assert low_wacc.fair_value_per_share > high_wacc.fair_value_per_share

    def test_net_debt_reduces_equity(self):
        no_debt = DCFModel.calculate(_make_dcf_input(net_debt=0))
        with_debt = DCFModel.calculate(_make_dcf_input(net_debt=100_000))
        assert no_debt.equity_value > with_debt.equity_value

    def test_sensitivity_table(self):
        result = DCFModel.calculate(_make_dcf_input())
        assert len(result.sensitivity) > 0
        # Each cell has wacc and terminal_growth
        cell = result.sensitivity[0]
        assert isinstance(cell, SensitivityCell)
        assert cell.wacc > 0
        assert cell.fair_value > 0

    def test_terminal_value_positive(self):
        result = DCFModel.calculate(_make_dcf_input())
        assert result.terminal_value > 0
        assert result.pv_terminal_value > 0

    def test_no_stage2(self):
        result = DCFModel.calculate(_make_dcf_input(stage2_years=0))
        assert len(result.projections) == 5  # only stage1
        assert result.fair_value_per_share > 0


# ── Comparable Tests ─────────────────────────────────────────────────────────

class TestComparableAnalysis:
    def test_basic_comparable(self):
        inputs = ComparableInput(
            target_ticker="AAPL",
            target_eps=6.50,
            target_ebitda=130.0,
            target_fcf_per_share=6.0,
            target_book_value=4.0,
            peers=_make_peers(),
        )
        result = ComparableAnalysis.analyze(inputs)
        assert isinstance(result, ComparableResult)
        assert result.peer_count == 4
        assert result.consensus_fair_value > 0

    def test_median_pe(self):
        inputs = ComparableInput(
            target_ticker="X",
            target_eps=5.0,
            peers=[
                PeerMultiple(ticker="A", pe_ratio=20.0),
                PeerMultiple(ticker="B", pe_ratio=30.0),
            ],
        )
        result = ComparableAnalysis.analyze(inputs)
        assert result.median_pe == 25.0  # median of [20, 30]
        assert result.implied_value_pe == 25.0 * 5.0  # 125.0

    def test_no_peers_returns_empty(self):
        result = ComparableAnalysis.analyze(ComparableInput(target_ticker="X"))
        assert result.consensus_fair_value == 0.0

    def test_partial_data(self):
        """Only PE available, no other multiples."""
        inputs = ComparableInput(
            target_ticker="X",
            target_eps=10.0,
            peers=[PeerMultiple(ticker="A", pe_ratio=15.0)],
        )
        result = ComparableAnalysis.analyze(inputs)
        assert result.consensus_fair_value > 0
        assert result.implied_value_pe == 150.0

    def test_weights_renormalize(self):
        """When only PE is available, it should get 100% weight."""
        inputs = ComparableInput(
            target_ticker="X",
            target_eps=10.0,
            peers=[PeerMultiple(ticker="A", pe_ratio=20.0)],
        )
        result = ComparableAnalysis.analyze(inputs)
        assert result.weights_used.get("pe", 0) == pytest.approx(1.0, abs=0.01)


# ── Margin of Safety Tests ───────────────────────────────────────────────────

class TestMarginOfSafety:
    def test_undervalued(self):
        m = MarginCalculator.calculate("X", fair_value=200.0, current_price=140.0)
        assert m.verdict == ValuationVerdict.UNDERVALUED
        assert m.margin_pct == pytest.approx(30.0, abs=0.1)

    def test_overvalued(self):
        m = MarginCalculator.calculate("X", fair_value=100.0, current_price=120.0)
        assert m.verdict == ValuationVerdict.OVERVALUED
        assert m.margin_pct < 0

    def test_fair_value_range(self):
        m = MarginCalculator.calculate("X", fair_value=100.0, current_price=95.0)
        assert m.verdict == ValuationVerdict.FAIR_VALUE

    def test_graham_number(self):
        gn = MarginCalculator.graham_number(eps=6.50, book_value_per_share=4.0)
        expected = math.sqrt(22.5 * 6.50 * 4.0)
        assert gn == pytest.approx(expected, abs=0.01)

    def test_graham_number_negative_eps(self):
        gn = MarginCalculator.graham_number(eps=-2.0, book_value_per_share=10.0)
        assert gn is None

    def test_graham_number_none(self):
        gn = MarginCalculator.graham_number(eps=None, book_value_per_share=None)
        assert gn is None

    def test_margin_includes_graham(self):
        m = MarginCalculator.calculate(
            "X", fair_value=150.0, current_price=100.0,
            eps=5.0, book_value_per_share=20.0,
        )
        assert m.graham_number is not None
        assert m.graham_number > 0


# ── Engine Integration Tests ─────────────────────────────────────────────────

class TestValuationEngine:
    def test_full_valuation_dcf_only(self):
        report = ValuationEngine.full_valuation(
            ticker="AAPL",
            current_price=175.0,
            dcf_input=_make_dcf_input(),
        )
        assert isinstance(report, ValuationReport)
        assert report.dcf is not None
        assert report.consensus_fair_value > 0

    def test_full_valuation_with_comps(self):
        report = ValuationEngine.full_valuation(
            ticker="AAPL",
            current_price=175.0,
            dcf_input=_make_dcf_input(),
            peers=_make_peers(),
            eps=6.50,
            book_value_per_share=4.0,
        )
        assert report.dcf is not None
        assert report.comparable is not None
        assert report.margin_of_safety is not None
        assert report.consensus_fair_value > 0

    def test_full_valuation_upside(self):
        report = ValuationEngine.full_valuation(
            ticker="X",
            current_price=50.0,
            dcf_input=_make_dcf_input(
                current_fcf=1000, shares_outstanding=100, net_debt=0
            ),
        )
        # Fair value should be >> $50 → positive upside
        if report.consensus_fair_value > 50:
            assert report.upside_pct > 0

    def test_derived_dcf_from_fundamentals(self):
        fundamental = FundamentalFeatureSet(
            ticker="AAPL",
            fcf_yield=0.035,
            market_cap=2_500_000.0,  # $2.5T
            revenue_growth_yoy=0.08,
            beta=1.2,
            debt_to_equity=1.8,
        )
        report = ValuationEngine.full_valuation(
            ticker="AAPL",
            current_price=175.0,
            fundamental=fundamental,
        )
        assert report.dcf is not None
        assert report.dcf.fair_value_per_share > 0


# ── Model Validation Tests ───────────────────────────────────────────────────

class TestModelValidation:
    def test_dcf_input_constraints(self):
        """Terminal growth can't exceed 5%."""
        with pytest.raises(Exception):
            DCFInput(
                current_fcf=1000, terminal_growth_rate=0.10,
                wacc=0.10, shares_outstanding=100,
            )

    def test_sensitivity_cell(self):
        cell = SensitivityCell(wacc=0.10, terminal_growth=0.025, fair_value=150.0)
        assert cell.wacc == 0.10
        assert cell.fair_value == 150.0
