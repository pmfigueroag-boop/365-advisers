"""tests/test_capital_allocation.py — Capital Allocation tests."""
import pytest
from src.engines.capital_allocation.models import AllocationMethod, StrategyBudget
from src.engines.capital_allocation.allocator import CapitalAllocator
from src.engines.capital_allocation.rebalancer import DriftDetector
from src.engines.capital_allocation.engine import CapitalAllocationEngine

def _strategies():
    return [
        StrategyBudget(strategy_id="momentum", volatility=0.20, recent_return=0.15, max_allocation=0.5),
        StrategyBudget(strategy_id="value", volatility=0.10, recent_return=0.05, max_allocation=0.5),
        StrategyBudget(strategy_id="quality", volatility=0.15, recent_return=0.10, max_allocation=0.5),
    ]

class TestAllocator:
    def test_equal_weight(self):
        r = CapitalAllocator.allocate(_strategies(), AllocationMethod.EQUAL)
        assert len(r.allocations) == 3
        assert all(abs(w - 1/3) < 0.01 for w in r.allocations.values())

    def test_risk_parity(self):
        r = CapitalAllocator.allocate(_strategies(), AllocationMethod.RISK_PARITY)
        # Lower vol → higher weight
        assert r.allocations["value"] > r.allocations["momentum"]

    def test_inverse_vol(self):
        r = CapitalAllocator.allocate(_strategies(), AllocationMethod.INVERSE_VOL)
        assert r.allocations["value"] > r.allocations["momentum"]

    def test_momentum_tilt(self):
        r = CapitalAllocator.allocate(_strategies(), AllocationMethod.MOMENTUM_TILT)
        # Higher return → higher weight
        assert r.allocations["momentum"] > r.allocations["value"]

    def test_risk_budget(self):
        r = CapitalAllocator.allocate(_strategies(), AllocationMethod.RISK_BUDGET)
        assert sum(r.allocations.values()) == pytest.approx(1.0, abs=0.01)

    def test_weights_sum_to_one(self):
        for method in AllocationMethod:
            r = CapitalAllocator.allocate(_strategies(), method)
            assert sum(r.allocations.values()) == pytest.approx(1.0, abs=0.01)

    def test_hhi_concentration(self):
        r = CapitalAllocator.allocate(_strategies(), AllocationMethod.EQUAL)
        assert r.analytics["hhi"] == pytest.approx(1/3, abs=0.01)

class TestDriftDetector:
    def test_no_drift(self):
        strats = [StrategyBudget(strategy_id="a", current_allocation=0.5, target_allocation=0.5)]
        dr = DriftDetector.detect_drift(strats)
        assert not dr.rebalance_needed

    def test_drift_detected(self):
        strats = [StrategyBudget(strategy_id="a", current_allocation=0.3, target_allocation=0.5)]
        dr = DriftDetector.detect_drift(strats, threshold=0.05)
        assert dr.rebalance_needed
        assert dr.max_drift == pytest.approx(0.2, abs=0.01)

    def test_rebalance_trades(self):
        strats = [
            StrategyBudget(strategy_id="a", current_allocation=0.3, target_allocation=0.5),
            StrategyBudget(strategy_id="b", current_allocation=0.7, target_allocation=0.5),
        ]
        trades = DriftDetector.compute_rebalance_trades(strats)
        assert len(trades) == 2
        increase = [t for t in trades if t.direction == "increase"]
        decrease = [t for t in trades if t.direction == "decrease"]
        assert len(increase) == 1
        assert len(decrease) == 1

class TestCapitalAllocationEngine:
    def test_allocate_and_drift(self):
        strats = _strategies()
        for s in strats:
            s.current_allocation = 0.33
        result = CapitalAllocationEngine.allocate(strats, AllocationMethod.RISK_PARITY)
        assert sum(result.allocations.values()) == pytest.approx(1.0, abs=0.01)
        drift = CapitalAllocationEngine.check_drift(strats, threshold=0.01)
        assert isinstance(drift.rebalance_needed, bool)
