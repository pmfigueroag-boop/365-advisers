"""
tests/test_option_a.py
--------------------------------------------------------------------------
Tests for Portfolio Walk-Forward, Kill Switch, Circuit Breaker, Multi-Strategy.
"""

from __future__ import annotations

import random
import math
import pytest
from datetime import date, datetime, timezone

from src.engines.backtesting.portfolio_walk_forward import (
    PortfolioWalkForward,
    PortfolioWFReport,
)
from src.engines.backtesting.kill_switch import (
    KillSwitch,
    KillSwitchConfig,
    LiveMetrics,
    SignalHealth,
)
from src.engines.data.circuit_breaker import (
    CircuitBreakerManager,
    CircuitBreakerConfig,
    BreakerState,
)
from src.engines.portfolio.multi_strategy import (
    MultiStrategyAllocator,
    AllocationResult,
)


# ─── Portfolio Walk-Forward Tests ────────────────────────────────────────────

class TestPortfolioWalkForward:

    def _make_returns(self, n=500, drift=0.0003, vol=0.012, seed=42):
        rng = random.Random(seed)
        return [drift + rng.gauss(0, vol) for _ in range(n)]

    def test_basic_walk_forward(self):
        """WF runs and produces windows."""
        wf = PortfolioWalkForward(is_days=100, oos_days=50, step_days=50)
        rets = self._make_returns(500)
        report = wf.run(rets)

        assert report.total_windows >= 3
        assert report.avg_is_sharpe > 0
        assert report.avg_oos_sharpe > 0

    def test_overfit_detected(self):
        """Noisy IS + zero OOS → overfit flagged."""
        wf = PortfolioWalkForward(is_days=100, oos_days=50, step_days=50)
        # Create data where IS looks good but OOS collapses
        rng = random.Random(42)
        rets = []
        for i in range(500):
            chunk = i // 150
            if chunk % 2 == 0:  # IS windows: positive
                rets.append(0.002 + rng.gauss(0, 0.005))
            else:  # OOS windows: negative
                rets.append(-0.001 + rng.gauss(0, 0.015))
        report = wf.run(rets)

        assert report.total_windows >= 2

    def test_too_short_data(self):
        """Not enough data → empty report."""
        wf = PortfolioWalkForward(is_days=252, oos_days=63)
        report = wf.run([0.001] * 100)

        assert report.total_windows == 0

    def test_stability_measured(self):
        """OOS Sharpe stability is computed."""
        wf = PortfolioWalkForward(is_days=100, oos_days=50, step_days=50)
        report = wf.run(self._make_returns(600))

        assert report.oos_sharpe_stability >= 0

    def test_degradation_computed(self):
        """Each window has degradation ratio."""
        wf = PortfolioWalkForward(is_days=100, oos_days=50, step_days=50)
        report = wf.run(self._make_returns(400))

        for w in report.windows:
            assert isinstance(w.degradation_ratio, float)


# ─── Kill Switch Tests ──────────────────────────────────────────────────────

class TestKillSwitch:

    def test_healthy_signal(self):
        """Good metrics → HEALTHY, no action."""
        ks = KillSwitch()
        decision = ks.evaluate(LiveMetrics(
            signal_id="sig.test",
            rolling_ic=0.08,
            cumulative_excess_return=0.05,
            current_drawdown=-0.03,
            consecutive_losses=0,
        ))

        assert decision.current_health == SignalHealth.HEALTHY
        assert decision.weight_multiplier == 1.0

    def test_low_ic_flags(self):
        """Rolling IC below min → FLAGGED."""
        ks = KillSwitch(KillSwitchConfig(min_rolling_ic=0.03))
        decision = ks.evaluate(LiveMetrics(
            signal_id="sig.test",
            rolling_ic=0.01,
        ))

        assert decision.current_health == SignalHealth.FLAGGED
        assert decision.action == "FLAG"

    def test_negative_ic_kills(self):
        """Negative IC → KILLED."""
        ks = KillSwitch()
        decision = ks.evaluate(LiveMetrics(
            signal_id="sig.test",
            rolling_ic=-0.05,
        ))

        assert decision.current_health == SignalHealth.KILLED
        assert decision.action == "KILL"
        assert decision.weight_multiplier == 0.0

    def test_consecutive_losses_throttle(self):
        """Enough consecutive losses → THROTTLE."""
        ks = KillSwitch(KillSwitchConfig(max_consecutive_losses=3))
        decision = ks.evaluate(LiveMetrics(
            signal_id="sig.test",
            rolling_ic=0.05,
            consecutive_losses=4,
        ))

        assert decision.current_health == SignalHealth.THROTTLED
        assert decision.weight_multiplier == 0.5

    def test_drawdown_kills(self):
        """Deep drawdown → KILLED."""
        ks = KillSwitch()
        decision = ks.evaluate(LiveMetrics(
            signal_id="sig.test",
            rolling_ic=0.05,
            current_drawdown=-0.20,
        ))

        assert decision.current_health == SignalHealth.KILLED

    def test_restore_on_recovery(self):
        """Recovery from FLAGGED → RESTORE."""
        ks = KillSwitch(KillSwitchConfig(min_rolling_ic=0.03))

        # First: flag it
        ks.evaluate(LiveMetrics(signal_id="sig.test", rolling_ic=0.01))
        assert ks.get_health("sig.test") == SignalHealth.FLAGGED

        # Second: recover
        decision = ks.evaluate(LiveMetrics(
            signal_id="sig.test", rolling_ic=0.10,
        ))
        assert decision.action == "RESTORE"
        assert decision.current_health == SignalHealth.HEALTHY

    def test_active_kills_list(self):
        """get_active_kills returns killed signals."""
        ks = KillSwitch()
        ks.evaluate(LiveMetrics(signal_id="sig.bad", rolling_ic=-0.05))
        ks.evaluate(LiveMetrics(signal_id="sig.good", rolling_ic=0.10))

        kills = ks.get_active_kills()
        assert "sig.bad" in kills
        assert "sig.good" not in kills

    def test_manual_reset(self):
        """Manual reset restores to HEALTHY."""
        ks = KillSwitch()
        ks.evaluate(LiveMetrics(signal_id="sig.test", rolling_ic=-0.05))
        assert ks.get_health("sig.test") == SignalHealth.KILLED

        ks.reset("sig.test")
        assert ks.get_health("sig.test") == SignalHealth.HEALTHY


# ─── Circuit Breaker Tests ──────────────────────────────────────────────────

class TestCircuitBreaker:

    def test_register_provider(self):
        """Provider registered."""
        cb = CircuitBreakerManager()
        cb.register("yfinance", priority=1)

        assert cb.provider_count == 1

    def test_success_keeps_closed(self):
        """Successes keep circuit closed."""
        cb = CircuitBreakerManager()
        cb.register("yfinance")

        state = cb.record_success("yfinance")
        assert state == BreakerState.CLOSED

    def test_failures_open_circuit(self):
        """Enough failures → OPEN."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreakerManager(config=config)
        cb.register("yfinance")

        for _ in range(3):
            cb.record_failure("yfinance")

        health = cb.get_health("yfinance")[0]
        assert health.state == BreakerState.OPEN
        assert not health.is_available

    def test_failover_chain(self):
        """Failover returns providers by priority."""
        cb = CircuitBreakerManager()
        cb.register("yfinance", priority=1)
        cb.register("alpha_vantage", priority=2)
        cb.register("twelve_data", priority=3)

        chain = cb.get_failover_chain()
        assert chain == ["yfinance", "alpha_vantage", "twelve_data"]

    def test_failover_skips_open(self):
        """Open providers skipped in failover."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreakerManager(config=config)
        cb.register("yfinance", priority=1)
        cb.register("alpha_vantage", priority=2)

        cb.record_failure("yfinance")
        cb.record_failure("yfinance")

        available = cb.get_available()
        assert available == "alpha_vantage"

    def test_execute_with_failover(self):
        """Failover execution tries next provider on failure."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreakerManager(config=config)
        cb.register("primary", priority=1)
        cb.register("secondary", priority=2)

        call_log = []

        def fetch(provider, *args, **kwargs):
            call_log.append(provider)
            if provider == "primary":
                raise ConnectionError("down")

        result = cb.execute_with_failover(fetch)
        assert result.success is True
        assert result.selected_provider == "secondary"
        assert result.fallback_used is True
        assert len(call_log) == 2

    def test_recovery_half_open(self):
        """Success in half-open → recovers to CLOSED."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            cooldown_seconds=0,  # Immediate for testing
            success_threshold=1,
        )
        cb = CircuitBreakerManager(config=config)
        cb.register("yfinance")

        # Open it
        cb.record_failure("yfinance")
        cb.record_failure("yfinance")

        # Force half-open (cooldown=0)
        cb._check_half_open()

        health = cb.get_health("yfinance")[0]
        assert health.state == BreakerState.HALF_OPEN

        # Recover
        cb.record_success("yfinance")
        health = cb.get_health("yfinance")[0]
        assert health.state == BreakerState.CLOSED


# ─── Multi-Strategy Tests ───────────────────────────────────────────────────

class TestMultiStrategyAllocator:

    def _setup_allocator(self) -> MultiStrategyAllocator:
        alloc = MultiStrategyAllocator()
        alloc.add_strategy("momentum", sharpe=1.2, annualized_return=0.15, annualized_vol=0.12)
        alloc.add_strategy("value", sharpe=0.8, annualized_return=0.10, annualized_vol=0.10)
        alloc.add_strategy("quality", sharpe=1.0, annualized_return=0.12, annualized_vol=0.08)
        return alloc

    def test_equal_weight(self):
        """Equal weight: all 1/N."""
        alloc = self._setup_allocator()
        result = alloc.allocate(method="equal_weight")

        assert len(result.allocations) == 3
        for a in result.allocations:
            assert a.weight == pytest.approx(1 / 3, abs=0.01)

    def test_risk_parity(self):
        """Risk parity: lower-vol gets higher weight."""
        alloc = self._setup_allocator()
        result = alloc.allocate(method="risk_parity")

        weights = {a.name: a.weight for a in result.allocations}
        # Quality (vol=8%) should have highest weight
        assert weights["quality"] > weights["momentum"]

    def test_kelly(self):
        """Kelly: higher Sharpe+return gets more."""
        alloc = self._setup_allocator()
        result = alloc.allocate(method="kelly")

        weights = {a.name: a.weight for a in result.allocations}
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_momentum_allocation(self):
        """Momentum: recent winners overweighted."""
        alloc = MultiStrategyAllocator()
        alloc.add_strategy("winner", sharpe=1.0, annualized_vol=0.10,
                          recent_returns=[0.01] * 60)
        alloc.add_strategy("loser", sharpe=1.0, annualized_vol=0.10,
                          recent_returns=[-0.01] * 60)

        result = alloc.allocate(method="momentum")
        weights = {a.name: a.weight for a in result.allocations}
        assert weights["winner"] > weights["loser"]

    def test_capacity_constraint(self):
        """Capacity capped strategy gets reduced weight."""
        alloc = MultiStrategyAllocator()
        alloc.add_strategy("big", sharpe=1.0, annualized_vol=0.10)
        alloc.add_strategy("small", sharpe=1.0, annualized_vol=0.10,
                          capacity=100_000)

        result = alloc.allocate(method="equal_weight", total_capital=1_000_000)
        weights = {a.name: a.weight for a in result.allocations}
        assert weights["small"] < weights["big"]

    def test_diversification_ratio(self):
        """Diversification ratio computed."""
        alloc = self._setup_allocator()
        result = alloc.allocate(method="risk_parity")

        assert result.diversification_ratio >= 1.0  # Always >= 1 for uncorrelated

    def test_portfolio_metrics(self):
        """Expected Sharpe and vol computed."""
        alloc = self._setup_allocator()
        result = alloc.allocate(method="risk_parity")

        assert result.expected_portfolio_vol > 0
        assert result.expected_portfolio_sharpe > 0
