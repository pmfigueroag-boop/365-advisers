"""
tests/test_phase5_portfolio_engine.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for Phase 5: Portfolio Construction Engine.

Tests validate:
  1. RiskBudgetEngine enforces all constraints correctly
  2. Rebalancer generates proper actions
  3. PortfolioEngine.build() produces a valid portfolio
"""

import pytest
from src.engines.portfolio.risk_budget import RiskBudgetEngine, RiskLimits
from src.engines.portfolio.rebalancer import Rebalancer


# ─── RiskBudgetEngine ─────────────────────────────────────────────────────────

class TestRiskBudgetEngine:

    def _positions(self):
        return [
            {"ticker": "AAPL", "target_weight": 8.0, "sector": "Technology", "role": "CORE", "volatility_atr": 2.5},
            {"ticker": "MSFT", "target_weight": 7.0, "sector": "Technology", "role": "CORE", "volatility_atr": 2.0},
            {"ticker": "NVDA", "target_weight": 6.0, "sector": "Technology", "role": "SATELLITE", "volatility_atr": 4.0},
            {"ticker": "JPM", "target_weight": 5.0, "sector": "Financials", "role": "CORE", "volatility_atr": 3.0},
        ]

    def test_no_violations(self):
        positions = [
            {"ticker": "AAPL", "target_weight": 5.0, "sector": "Technology", "role": "CORE", "volatility_atr": 2.0},
            {"ticker": "JPM", "target_weight": 4.0, "sector": "Financials", "role": "CORE", "volatility_atr": 2.5},
        ]
        result = RiskBudgetEngine().evaluate(positions)
        assert result.passed is True
        assert len(result.violations) == 0
        assert result.total_allocation == 9.0

    def test_single_position_cap(self):
        positions = [
            {"ticker": "AAPL", "target_weight": 15.0, "sector": "Technology", "role": "CORE", "volatility_atr": 2.0},
        ]
        result = RiskBudgetEngine().evaluate(positions)
        assert any("capped" in v for v in result.violations)
        assert result.positions[0]["target_weight"] == 10.0

    def test_sector_concentration_cap(self):
        positions = self._positions()  # Tech = 21%
        result = RiskBudgetEngine().evaluate(positions)
        tech_exposure = result.sector_exposures.get("Technology", 0)
        assert tech_exposure <= 25.0

    def test_total_allocation_cap(self):
        positions = [
            {"ticker": f"T{i}", "target_weight": 10.0, "sector": f"Sec{i}", "role": "CORE", "volatility_atr": 2.0}
            for i in range(12)  # 120% total
        ]
        result = RiskBudgetEngine().evaluate(positions)
        assert result.total_allocation <= 100.0
        assert any("exceeded" in v for v in result.violations)

    def test_min_position_filter(self):
        positions = [
            {"ticker": "AAPL", "target_weight": 5.0, "sector": "Technology", "role": "CORE", "volatility_atr": 2.0},
            {"ticker": "TINY", "target_weight": 0.2, "sector": "Other", "role": "SATELLITE", "volatility_atr": 1.0},
        ]
        result = RiskBudgetEngine().evaluate(positions)
        tickers = [p["ticker"] for p in result.positions]
        assert "TINY" not in tickers

    def test_custom_limits(self):
        limits = RiskLimits(max_single_position=5.0)
        positions = [
            {"ticker": "AAPL", "target_weight": 7.0, "sector": "Technology", "role": "CORE", "volatility_atr": 2.0},
        ]
        result = RiskBudgetEngine(limits).evaluate(positions)
        assert result.positions[0]["target_weight"] == 5.0


# ─── Rebalancer ──────────────────────────────────────────────────────────────

class TestRebalancer:

    def test_no_rebalance_needed(self):
        current = {"AAPL": 5.0, "MSFT": 5.0}
        targets = [{"ticker": "AAPL", "target_weight": 5.0}, {"ticker": "MSFT", "target_weight": 5.0}]
        result = Rebalancer(threshold_pct=2.0).compute(current, targets)
        assert result.needs_rebalance is False
        assert all(a.action == "HOLD" for a in result.actions)

    def test_buy_action(self):
        current = {"AAPL": 3.0}
        targets = [{"ticker": "AAPL", "target_weight": 8.0}]
        result = Rebalancer(threshold_pct=2.0).compute(current, targets)
        assert result.needs_rebalance is True
        assert result.actions[0].action == "BUY"
        assert result.actions[0].drift == 5.0

    def test_sell_action(self):
        current = {"AAPL": 10.0}
        targets = [{"ticker": "AAPL", "target_weight": 5.0}]
        result = Rebalancer(threshold_pct=2.0).compute(current, targets)
        assert result.actions[0].action == "SELL"
        assert result.actions[0].drift == -5.0

    def test_exit_action(self):
        current = {"AAPL": 5.0}
        targets = []
        result = Rebalancer().compute(current, targets)
        assert result.actions[0].action == "EXIT"

    def test_new_action(self):
        current = {}
        targets = [{"ticker": "AAPL", "target_weight": 5.0}]
        result = Rebalancer().compute(current, targets)
        assert result.actions[0].action == "NEW"

    def test_custom_threshold(self):
        current = {"AAPL": 5.0}
        targets = [{"ticker": "AAPL", "target_weight": 6.0}]
        # 1% drift < 2% threshold → HOLD
        result = Rebalancer(threshold_pct=2.0).compute(current, targets)
        assert result.actions[0].action == "HOLD"
        # 1% drift > 0.5% threshold → BUY
        result2 = Rebalancer(threshold_pct=0.5).compute(current, targets)
        assert result2.actions[0].action == "BUY"

    def test_summary(self):
        current = {"AAPL": 3.0, "MSFT": 10.0}
        targets = [
            {"ticker": "AAPL", "target_weight": 8.0},
            {"ticker": "MSFT", "target_weight": 5.0},
        ]
        result = Rebalancer().compute(current, targets)
        assert "buy" in result.summary.lower()
        assert "sell" in result.summary.lower()


# ─── PortfolioEngine ─────────────────────────────────────────────────────────

class TestPortfolioEngine:

    def _sample_analyses(self):
        return [
            {
                "ticker": "AAPL", "sector": "Technology",
                "opportunity_score": 8.5,
                "dimensions": {"business_quality": 9, "financial_strength": 8},
                "position_sizing": {"suggested_allocation": 6.5, "risk_level": "NORMAL"},
            },
            {
                "ticker": "JPM", "sector": "Financials",
                "opportunity_score": 7.0,
                "dimensions": {"business_quality": 7, "financial_strength": 7},
                "position_sizing": {"suggested_allocation": 3.5, "risk_level": "NORMAL"},
            },
            {
                "ticker": "TSLA", "sector": "Automotive",
                "opportunity_score": 6.0,
                "dimensions": {"business_quality": 5, "financial_strength": 4},
                "position_sizing": {"suggested_allocation": 1.5, "risk_level": "ELEVATED"},
            },
        ]

    def test_build_basic(self):
        from src.engines.portfolio.engine import PortfolioEngine
        result = PortfolioEngine.build(self._sample_analyses())
        assert "total_allocation" in result
        assert "core_positions" in result
        assert "satellite_positions" in result
        assert result["total_allocation"] > 0

    def test_build_has_positions(self):
        from src.engines.portfolio.engine import PortfolioEngine
        result = PortfolioEngine.build(self._sample_analyses())
        all_pos = result["core_positions"] + result["satellite_positions"]
        tickers = [p["ticker"] for p in all_pos]
        assert "AAPL" in tickers
        assert "JPM" in tickers

    def test_build_sector_exposures(self):
        from src.engines.portfolio.engine import PortfolioEngine
        result = PortfolioEngine.build(self._sample_analyses())
        assert "Technology" in result["sector_exposures"]

    def test_build_empty(self):
        from src.engines.portfolio.engine import PortfolioEngine
        result = PortfolioEngine.build([])
        assert result["total_allocation"] == 0
