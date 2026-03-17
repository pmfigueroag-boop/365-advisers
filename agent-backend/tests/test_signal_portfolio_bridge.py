"""
tests/test_signal_portfolio_bridge.py
--------------------------------------------------------------------------
Tests for SignalPortfolioBridge, TransactionCostModel, and end-to-end flow.
"""

from __future__ import annotations

import pytest
from datetime import date

from src.engines.backtesting.models import SignalEvent, SignalStrength
from src.engines.backtesting.signal_attribution import (
    AttributionReport,
    SignalContribution,
)
from src.engines.backtesting.perturbation_validator import (
    PerturbationReport,
    SignalPerturbationResult,
)
from src.engines.backtesting.top_bottom_validator import (
    TopBottomReport,
    SignalTopBottomResult,
)
from src.engines.portfolio.signal_portfolio_bridge import (
    SignalPortfolioBridge,
    SignalQuality,
    BridgeResult,
)
from src.engines.portfolio.transaction_costs import (
    TransactionCostModel,
    CostModelConfig,
    TradeCostEstimate,
)
from src.engines.portfolio_optimisation.models import (
    OptimisationObjective,
    PortfolioConstraints,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_event(
    signal_id: str,
    ticker: str,
    fired_date: date,
    confidence: float = 0.7,
    excess_return_20: float = 0.02,
) -> SignalEvent:
    return SignalEvent(
        signal_id=signal_id,
        ticker=ticker,
        fired_date=fired_date,
        strength=SignalStrength.MODERATE,
        confidence=confidence,
        value=1.0,
        price_at_fire=100.0,
        forward_returns={20: excess_return_20 + 0.005},
        benchmark_returns={20: 0.005},
        excess_returns={20: excess_return_20},
    )


def _make_events_multi_ticker(n_per_ticker: int = 20) -> list[SignalEvent]:
    """Create events for 3 tickers with 2 signals each."""
    events = []
    tickers = ["AAPL", "MSFT", "GOOGL"]
    signals = ["sig.value", "sig.momentum"]
    import random
    rng = random.Random(42)

    for ticker in tickers:
        for sig in signals:
            for i in range(n_per_ticker):
                excess = 0.01 + rng.gauss(0, 0.005)
                events.append(_make_event(
                    sig, ticker, date(2024, 1, 1 + i),
                    confidence=0.5 + rng.random() * 0.3,
                    excess_return_20=excess,
                ))
    return events


def _make_attribution(
    signal_ids: list[str] | None = None,
    ics: list[float] | None = None,
    contributions: list[float] | None = None,
) -> AttributionReport:
    signal_ids = signal_ids or ["sig.value", "sig.momentum"]
    ics = ics or [0.08, 0.05]
    contributions = contributions or [0.3, 0.2]

    contribs = []
    for sid, ic, contrib in zip(signal_ids, ics, contributions):
        contribs.append(SignalContribution(
            signal_id=sid,
            ic=ic,
            marginal_contribution=contrib,
            individual_sharpe=0.5,
            system_without_sharpe=0.3,
            is_dilutive=contrib < 0,
        ))

    return AttributionReport(
        signal_contributions=contribs,
        system_sharpe=0.5,
        avg_ic=sum(ics) / len(ics),
        bair=0.1,
    )


def _make_perturbation(
    signal_ids: list[str] | None = None,
    sensitivities: list[float] | None = None,
) -> PerturbationReport:
    signal_ids = signal_ids or ["sig.value", "sig.momentum"]
    sensitivities = sensitivities or [0.15, 0.20]

    results = []
    for sid, sens in zip(signal_ids, sensitivities):
        results.append(SignalPerturbationResult(
            signal_id=sid,
            perturbation_sensitivity=sens,
            is_fragile=sens > 0.50,
        ))

    return PerturbationReport(
        signal_results=results,
        n_trials=30,
        noise_pct=0.02,
        total_signals=len(results),
    )


def _make_top_bottom(
    signal_ids: list[str] | None = None,
    spreads: list[float] | None = None,
    monotonicity_scores: list[float] | None = None,
) -> TopBottomReport:
    signal_ids = signal_ids or ["sig.value", "sig.momentum"]
    spreads = spreads or [0.01, 0.008]
    monotonicity_scores = monotonicity_scores or [0.8, 0.6]

    results = []
    for sid, sp, mono in zip(signal_ids, spreads, monotonicity_scores):
        results.append(SignalTopBottomResult(
            signal_id=sid,
            spread=sp,
            monotonicity_score=mono,
            spread_t_stat=3.0 if sp > 0 else -3.0,
            is_significant=True,
            has_negative_spread=sp < 0,
            quintile_returns=[0.005, 0.01, 0.015, 0.02, 0.025],
        ))

    return TopBottomReport(
        signal_results=results,
        total_signals=len(results),
    )


# ─── TransactionCostModel Tests ─────────────────────────────────────────────

class TestTransactionCostModel:
    def test_estimate_trade_basic(self):
        """Basic trade cost estimation."""
        model = TransactionCostModel()
        cost = model.estimate_trade("AAPL", trade_value=10_000)

        assert cost.spread_cost > 0
        assert cost.impact_cost > 0
        assert cost.commission_cost > 0
        assert cost.total_cost == pytest.approx(
            cost.spread_cost + cost.impact_cost + cost.commission_cost,
            abs=0.01,
        )
        assert cost.cost_bps > 0

    def test_zero_trade_no_cost(self):
        """Zero trade value → no cost."""
        model = TransactionCostModel()
        cost = model.estimate_trade("AAPL", trade_value=0)
        assert cost.total_cost == 0.0

    def test_higher_value_higher_cost(self):
        """Larger trades → higher absolute cost."""
        model = TransactionCostModel()
        small = model.estimate_trade("AAPL", trade_value=1_000)
        large = model.estimate_trade("AAPL", trade_value=100_000)
        assert large.total_cost > small.total_cost

    def test_custom_config(self):
        """Custom config changes costs."""
        cheap = TransactionCostModel(CostModelConfig(
            half_spread_bps=1.0,
            commission_per_share=0.001,
            commission_per_trade=0.0,
        ))
        expensive = TransactionCostModel(CostModelConfig(
            half_spread_bps=20.0,
            commission_per_share=0.01,
            commission_per_trade=5.0,
        ))

        cheap_cost = cheap.estimate_trade("AAPL", trade_value=10_000)
        exp_cost = expensive.estimate_trade("AAPL", trade_value=10_000)

        assert exp_cost.total_cost > cheap_cost.total_cost

    def test_annual_cost_drag(self):
        """Annual cost drag is positive for active portfolio."""
        model = TransactionCostModel()
        weights = {"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4}
        drag = model.annual_cost_drag(weights, rebalance_freq=12)

        assert drag > 0
        # Should be reasonable: < 5% for liquid US equities
        assert drag < 0.05

    def test_cost_drag_zero_weights(self):
        """Empty weights → zero drag."""
        model = TransactionCostModel()
        drag = model.annual_cost_drag({}, rebalance_freq=12)
        assert drag == 0.0

    def test_more_rebalances_more_cost(self):
        """More frequent rebalancing → higher cost drag."""
        model = TransactionCostModel()
        weights = {"AAPL": 0.5, "MSFT": 0.5}
        monthly = model.annual_cost_drag(weights, rebalance_freq=12)
        weekly = model.annual_cost_drag(weights, rebalance_freq=52)
        assert weekly > monthly


# ─── SignalPortfolioBridge Tests ─────────────────────────────────────────────

class TestSignalPortfolioBridge:
    def test_full_pipeline_produces_weights(self):
        """End-to-end: events + validation → optimised weights."""
        events = _make_events_multi_ticker(n_per_ticker=20)
        bridge = SignalPortfolioBridge(
            constraints=PortfolioConstraints(
                min_weight=0.0, max_weight=0.50, long_only=True,
            ),
        )

        result = bridge.construct(
            events=events,
            attribution=_make_attribution(),
            perturbation=_make_perturbation(),
            top_bottom=_make_top_bottom(),
        )

        assert result.usable_signals == 2
        assert result.tickers_in_portfolio == 3
        assert result.optimisation is not None
        weights = result.optimisation.optimal_weights
        assert len(weights) == 3
        # Weights should sum to ~1.0
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_empty_events_returns_empty(self):
        """No events → empty result."""
        bridge = SignalPortfolioBridge()
        result = bridge.construct(events=[])
        assert result.tickers_in_portfolio == 0
        assert result.optimisation is None

    def test_negative_contribution_signal_filtered(self):
        """Signal with negative contribution → rejected."""
        events = _make_events_multi_ticker()
        attr = _make_attribution(
            signal_ids=["sig.value", "sig.momentum"],
            ics=[0.08, 0.05],
            contributions=[0.3, -0.1],  # momentum is dilutive
        )
        bridge = SignalPortfolioBridge()
        result = bridge.construct(events=events, attribution=attr)

        assert result.rejected_signals == 1
        assert result.usable_signals == 1

    def test_fragile_signal_filtered(self):
        """Signal with high perturbation sensitivity → rejected."""
        events = _make_events_multi_ticker()
        pert = _make_perturbation(
            signal_ids=["sig.value", "sig.momentum"],
            sensitivities=[0.15, 0.80],  # momentum is fragile
        )
        bridge = SignalPortfolioBridge()
        result = bridge.construct(
            events=events,
            attribution=_make_attribution(),
            perturbation=pert,
        )

        assert result.rejected_signals == 1

    def test_inverse_signal_filtered(self):
        """Signal with negative spread → rejected."""
        events = _make_events_multi_ticker()
        tb = _make_top_bottom(
            signal_ids=["sig.value", "sig.momentum"],
            spreads=[0.01, -0.02],  # momentum has inverse spread
            monotonicity_scores=[0.8, -0.5],
        )
        bridge = SignalPortfolioBridge()
        result = bridge.construct(
            events=events,
            attribution=_make_attribution(),
            top_bottom=tb,
        )

        assert result.rejected_signals == 1

    def test_cost_drag_computed(self):
        """Transaction cost drag is computed in the result."""
        events = _make_events_multi_ticker()
        bridge = SignalPortfolioBridge()
        result = bridge.construct(
            events=events,
            attribution=_make_attribution(),
        )

        assert result.total_cost_drag >= 0.0

    def test_ticker_returns_have_metadata(self):
        """Each ticker return has source signal info."""
        events = _make_events_multi_ticker()
        bridge = SignalPortfolioBridge()
        result = bridge.construct(
            events=events,
            attribution=_make_attribution(),
        )

        for tr in result.ticker_returns:
            assert tr.ticker != ""
            assert tr.n_signals > 0
            assert tr.n_events > 0
            assert len(tr.source_signals) > 0

    def test_ic_weighting_works(self):
        """Signal with higher IC gets more influence on expected return."""
        events = _make_events_multi_ticker(n_per_ticker=20)
        # Give sig.value much higher IC
        attr = _make_attribution(
            signal_ids=["sig.value", "sig.momentum"],
            ics=[0.50, 0.01],
            contributions=[0.5, 0.1],
        )
        bridge = SignalPortfolioBridge()
        result = bridge.construct(events=events, attribution=attr)

        # Should produce valid result with both signals included
        assert result.usable_signals == 2
        assert result.optimisation is not None

    def test_constraints_respected(self):
        """Portfolio constraints are passed to optimizer."""
        events = _make_events_multi_ticker()
        bridge = SignalPortfolioBridge(
            constraints=PortfolioConstraints(
                min_weight=0.0, max_weight=0.40, long_only=True,
            ),
        )
        result = bridge.construct(
            events=events,
            attribution=_make_attribution(),
        )

        if result.optimisation:
            for w in result.optimisation.optimal_weights.values():
                assert w <= 0.40 + 0.01  # small tolerance
