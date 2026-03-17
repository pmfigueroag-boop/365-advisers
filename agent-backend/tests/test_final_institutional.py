"""
tests/test_final_institutional.py
--------------------------------------------------------------------------
Tests for FactorNeutralConstraints, SurvivorshipBiasController, TCAEngine.
"""

from __future__ import annotations

import pytest
from datetime import date, datetime, timezone

from src.engines.portfolio_optimisation.factor_neutral import (
    FactorNeutralConstraints,
    FactorExposure,
    NeutralizationResult,
)
from src.engines.backtesting.survivorship_bias import (
    SurvivorshipBiasController,
    BiasReport,
)
from src.engines.portfolio.tca import (
    TCAEngine,
    OrderFill,
    TCAReport,
)
from src.engines.backtesting.models import SignalEvent, SignalStrength


# ─── FactorNeutral Tests ────────────────────────────────────────────────────

class TestFactorNeutralConstraints:

    def test_already_neutral(self):
        """Portfolio already at target beta → no adjustment."""
        fn = FactorNeutralConstraints(target_beta=1.0, beta_tolerance=0.1)
        result = fn.neutralize(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            betas={"AAPL": 1.0, "MSFT": 1.0},
        )

        assert result.adjustment_magnitude == 0.0
        assert result.exposure_before.is_neutral is True

    def test_high_beta_reduced(self):
        """High-beta portfolio is adjusted toward target."""
        fn = FactorNeutralConstraints(target_beta=0.0, beta_tolerance=0.1)
        result = fn.neutralize(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            betas={"AAPL": 1.5, "MSFT": 0.5},
        )

        # After neutralization, beta should be closer to 0
        assert abs(result.exposure_after.portfolio_beta) < abs(result.exposure_before.portfolio_beta)

    def test_exposure_computation(self):
        """Exposure correctly computed as weighted sum."""
        fn = FactorNeutralConstraints()
        exposures = {
            "AAPL": FactorExposure(ticker="AAPL", beta=1.2, value=-0.3),
            "MSFT": FactorExposure(ticker="MSFT", beta=0.8, value=0.5),
        }
        exp = fn.compute_exposure(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            factor_exposures=exposures,
        )

        assert exp.portfolio_beta == pytest.approx(1.0, abs=0.01)
        assert exp.value_exposure == pytest.approx(0.1, abs=0.01)

    def test_violations_detected(self):
        """Violations listed when out of tolerance."""
        fn = FactorNeutralConstraints(target_beta=0.0, beta_tolerance=0.05)
        exp = fn.compute_exposure(
            weights={"AAPL": 1.0},
            factor_exposures={"AAPL": FactorExposure(ticker="AAPL", beta=1.2)},
        )

        assert len(exp.violations) > 0
        assert "Beta" in exp.violations[0]

    def test_beta_estimation(self):
        """Beta estimated from returns."""
        import random
        rng = random.Random(42)
        market = [rng.gauss(0.001, 0.01) for _ in range(100)]
        # AAPL has beta ~1.5 (amplified market returns)
        aapl = [1.5 * m + rng.gauss(0, 0.005) for m in market]
        # MSFT has beta ~0.5 (dampened)
        msft = [0.5 * m + rng.gauss(0, 0.005) for m in market]

        betas = FactorNeutralConstraints.estimate_betas(
            asset_returns={"AAPL": aapl, "MSFT": msft},
            market_returns=market,
        )

        assert betas["AAPL"] > 1.0
        assert betas["MSFT"] < 1.0

    def test_factor_limits_enforced(self):
        """Factor limits create violations."""
        fn = FactorNeutralConstraints(
            target_beta=1.0,
            beta_tolerance=0.5,
            factor_limits={"value": (-0.1, 0.1)},
        )
        exp = fn.compute_exposure(
            weights={"AAPL": 1.0},
            factor_exposures={"AAPL": FactorExposure(ticker="AAPL", beta=1.0, value=0.5)},
        )

        assert not exp.is_neutral
        assert any("value" in v for v in exp.violations)

    def test_neutralize_reduces_beta(self):
        """Neutralize on beta=1.0 portfolio → closer to 0."""
        fn = FactorNeutralConstraints(target_beta=0.0, beta_tolerance=0.2)
        result = fn.neutralize(
            weights={"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
            betas={"A": 1.5, "B": 1.3, "C": 0.7, "D": 0.5},
        )

        assert abs(result.exposure_after.portfolio_beta) < 1.0
        assert result.iterations > 0


# ─── SurvivorshipBias Tests ─────────────────────────────────────────────────

class TestSurvivorshipBiasController:

    def test_register_delisted(self):
        """Delisted ticker registered."""
        ctrl = SurvivorshipBiasController()
        entry = ctrl.register_delisted(
            "LUMN", date(2023, 6, 1), "acquired", terminal_return=-0.95,
        )

        assert ctrl.delisted_count == 1
        assert ctrl.is_delisted("LUMN")
        assert not ctrl.is_delisted("AAPL")

    def test_was_active_on(self):
        """Active check respects delist date."""
        ctrl = SurvivorshipBiasController()
        ctrl.register_delisted("GE", date(2023, 1, 1), "restructured")

        assert ctrl.was_active_on("GE", date(2022, 12, 31))
        assert not ctrl.was_active_on("GE", date(2023, 1, 2))

    def test_universe_includes_delisted_before_delist(self):
        """Point-in-time universe includes tickers not yet delisted."""
        ctrl = SurvivorshipBiasController()
        ctrl.register_snapshot(
            date(2020, 1, 1),
            ["AAPL", "MSFT", "LUMN"],
        )
        ctrl.register_delisted("LUMN", date(2022, 6, 1), "acquired")

        # In 2021, LUMN was still active
        universe = ctrl.get_universe_at(date(2021, 6, 1))
        assert "LUMN" in universe

        # After delist, LUMN still in snapshot but marked
        universe_after = ctrl.get_universe_at(date(2023, 1, 1))
        assert "LUMN" in universe_after  # In snapshot, delist doesn't remove from snapshot

    def test_analyze_bias_detects_missing(self):
        """Bias analysis detects delisted missing from backtest."""
        ctrl = SurvivorshipBiasController()
        ctrl.register_delisted("FAIL1", date(2021, 1, 1), "bankruptcy", -1.0)
        ctrl.register_delisted("FAIL2", date(2022, 1, 1), "bankruptcy", -0.8)
        ctrl.set_current_universe(["AAPL", "MSFT", "GOOGL"])

        # Create events that don't include FAIL1, FAIL2
        events = [
            SignalEvent(
                signal_id="sig.test",
                ticker="AAPL",
                fired_date=date(2020, 6, 1),
                strength=SignalStrength.MODERATE,
                confidence=0.7,
                value=1.0,
                price_at_fire=100.0,
                forward_returns={},
                benchmark_returns={},
                excess_returns={},
            ),
        ]

        report = ctrl.analyze_bias(events)
        assert report.estimated_bias_bps > 0

    def test_look_ahead_violation(self):
        """Events after delist date → look-ahead violation."""
        ctrl = SurvivorshipBiasController()
        ctrl.register_delisted("FAIL", date(2021, 6, 1), "bankruptcy")

        event = SignalEvent(
            signal_id="sig.test",
            ticker="FAIL",
            fired_date=date(2022, 1, 1),  # After delist!
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            value=1.0,
            price_at_fire=100.0,
            forward_returns={},
            benchmark_returns={},
            excess_returns={},
        )

        report = ctrl.analyze_bias([event])
        assert report.look_ahead_violations == 1

    def test_snapshot_count(self):
        """Snapshots counted."""
        ctrl = SurvivorshipBiasController()
        ctrl.register_snapshot(date(2020, 1, 1), ["A", "B"])
        ctrl.register_snapshot(date(2021, 1, 1), ["A", "B", "C"])

        assert ctrl.snapshot_count == 2


# ─── TCA Tests ──────────────────────────────────────────────────────────────

class TestTCAEngine:

    def _make_fill(
        self,
        ticker: str = "AAPL",
        decision_price: float = 150.0,
        fill_price: float = 150.5,
        vwap: float = 150.2,
        shares: int = 100,
        side: str = "BUY",
        order_id: str = "ORD-001",
    ) -> OrderFill:
        return OrderFill(
            order_id=order_id,
            ticker=ticker,
            side=side,
            decision_price=decision_price,
            fill_price=fill_price,
            shares=shares,
            fill_value=fill_price * shares,
            vwap=vwap,
            fill_date=date(2024, 6, 1),
        )

    def test_implementation_shortfall_buy(self):
        """BUY: paid more than decision → positive IS."""
        tca = TCAEngine()
        fill = self._make_fill(
            decision_price=150.0, fill_price=150.5, side="BUY",
        )
        analysis = tca.record_fill(fill)

        # IS = (150.5 - 150.0) / 150.0 = 0.00333 = 33.3 bps
        assert analysis.implementation_shortfall_bps > 0
        assert analysis.implementation_shortfall_bps == pytest.approx(33.33, abs=1)

    def test_implementation_shortfall_sell(self):
        """SELL: received less than decision → positive IS."""
        tca = TCAEngine()
        fill = self._make_fill(
            decision_price=150.0, fill_price=149.5, side="SELL",
        )
        analysis = tca.record_fill(fill)

        # IS for sell = -(149.5 - 150.0) / 150.0 = 33.3 bps
        assert analysis.implementation_shortfall_bps > 0

    def test_vwap_beat(self):
        """Fill below VWAP on a buy → beat VWAP."""
        tca = TCAEngine()
        fill = self._make_fill(
            decision_price=150.0, fill_price=149.8,
            vwap=150.0, side="BUY",
        )
        analysis = tca.record_fill(fill)

        assert analysis.beat_vwap is True
        assert analysis.vs_vwap_bps < 0

    def test_vwap_missed(self):
        """Fill above VWAP on a buy → missed VWAP."""
        tca = TCAEngine()
        fill = self._make_fill(
            decision_price=150.0, fill_price=150.5,
            vwap=150.0, side="BUY",
        )
        analysis = tca.record_fill(fill)

        assert analysis.beat_vwap is False

    def test_aggregate_report(self):
        """Aggregate TCA computes averages."""
        tca = TCAEngine()
        tca.record_fill(self._make_fill(
            order_id="O1", fill_price=150.5, decision_price=150.0,
        ))
        tca.record_fill(self._make_fill(
            order_id="O2", fill_price=149.8, decision_price=150.0,
        ))

        report = tca.analyze()
        assert report.total_fills == 2
        assert report.total_volume > 0

    def test_slippage_tracking(self):
        """Slippage in dollars computed correctly."""
        tca = TCAEngine()
        fill = self._make_fill(
            decision_price=100.0, fill_price=100.50,
            shares=200, side="BUY",
        )
        analysis = tca.record_fill(fill)

        # Slippage = |100.50 - 100.0| × 200 = $100
        assert analysis.slippage_dollars == pytest.approx(100.0, abs=0.1)

    def test_filter_by_ticker(self):
        """Report can filter by ticker."""
        tca = TCAEngine()
        tca.record_fill(self._make_fill(order_id="O1", ticker="AAPL"))
        tca.record_fill(self._make_fill(order_id="O2", ticker="MSFT"))

        report = tca.analyze(ticker="AAPL")
        assert report.total_fills == 1

    def test_perfect_execution(self):
        """Fill at decision price → zero IS."""
        tca = TCAEngine()
        fill = self._make_fill(
            decision_price=150.0, fill_price=150.0, vwap=150.0,
        )
        analysis = tca.record_fill(fill)

        assert analysis.implementation_shortfall_bps == 0.0
        assert analysis.slippage_dollars == 0.0

    def test_slippage_by_ticker(self):
        """Per-ticker slippage breakdown."""
        tca = TCAEngine()
        tca.record_fill(self._make_fill(
            order_id="O1", ticker="AAPL",
            decision_price=150.0, fill_price=150.5, shares=100,
        ))
        tca.record_fill(self._make_fill(
            order_id="O2", ticker="MSFT",
            decision_price=300.0, fill_price=302.0, shares=50,
        ))

        report = tca.analyze()
        assert "AAPL" in report.slippage_by_ticker
        assert "MSFT" in report.slippage_by_ticker
        assert report.slippage_by_ticker["MSFT"] > report.slippage_by_ticker["AAPL"]

    def test_empty_report(self):
        """No fills → empty report."""
        tca = TCAEngine()
        report = tca.analyze()
        assert report.total_fills == 0
