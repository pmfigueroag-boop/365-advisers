"""Integration test for Strategy Portfolio Lab with synthetic data."""
import sys
import os
import traceback
import random

sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_spl.db")

passed = 0
failed = 0


def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"[PASS] {name}")
        passed += 1
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        traceback.print_exc()
        failed += 1


# ── Synthetic data ──

def make_synthetic_data(n_dates=120, tickers=None):
    if tickers is None:
        tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "META", "TSLA", "JPM"]

    random.seed(42)
    dates = [f"2025-{m:02d}-{d:02d}" for m in range(1, 7) for d in range(1, 21)][:n_dates]

    prices = {}
    for ticker in tickers:
        base = random.uniform(100, 500)
        prices[ticker] = {}
        for d in dates:
            base *= (1 + random.gauss(0.001, 0.02))
            prices[ticker][d] = round(base, 2)

    signals_by_date = {}
    categories = ["momentum", "quality", "value"]
    for d in dates:
        sigs = []
        for ticker in tickers:
            if random.random() > 0.4:
                sigs.append({
                    "signal_id": f"sig_{ticker}_{d}", "ticker": ticker,
                    "category": random.choice(categories),
                    "strength": random.choice(["strong", "moderate", "weak"]),
                    "confidence": round(random.uniform(0.3, 0.95), 2),
                })
        signals_by_date[d] = sigs

    scores_by_date = {}
    for d in dates:
        scores_by_date[d] = {
            ticker: {
                "case_score": random.randint(40, 95),
                "uos": round(random.uniform(4.0, 9.5), 1),
                "opportunity_score": round(random.uniform(4.0, 9.5), 1),
            }
            for ticker in tickers
        }

    regime_cycle = ["bull", "bull", "bull", "range", "bear", "bear", "high_vol", "range"]
    regimes_by_date = {d: regime_cycle[i % len(regime_cycle)] for i, d in enumerate(dates)}

    bm_base = 450.0
    benchmark_prices = {}
    for d in dates:
        bm_base *= (1 + random.gauss(0.0005, 0.015))
        benchmark_prices[d] = round(bm_base, 2)

    liquidity = {t: random.uniform(50_000_000, 500_000_000) for t in tickers}

    return {
        "prices": prices, "signals_by_date": signals_by_date,
        "scores_by_date": scores_by_date, "regimes_by_date": regimes_by_date,
        "benchmark_prices": benchmark_prices, "liquidity": liquidity,
    }


data = make_synthetic_data()

# Strategy configs
momentum_config = {
    "name": "Momentum Quality",
    "signals": {"required_categories": ["momentum", "quality"], "min_confidence": "medium"},
    "thresholds": {"min_case_score": 60},
    "portfolio": {"max_positions": 8, "sizing_method": "equal"},
    "rebalance": {"frequency": "weekly"},
    "entry_rules": [{"field": "case_score", "operator": "gte", "value": 60}],
    "exit_rules": [], "regime_rules": [],
}

value_config = {
    "name": "Value Contrarian",
    "signals": {"required_categories": ["value"], "min_confidence": "low"},
    "thresholds": {"min_case_score": 50},
    "portfolio": {"max_positions": 10, "sizing_method": "equal"},
    "rebalance": {"frequency": "monthly"},
    "entry_rules": [{"field": "case_score", "operator": "gte", "value": 55}],
    "exit_rules": [], "regime_rules": [],
}

quality_config = {
    "name": "Quality Growth",
    "signals": {"required_categories": ["quality"], "min_confidence": "high"},
    "thresholds": {"min_case_score": 70},
    "portfolio": {"max_positions": 6, "sizing_method": "equal"},
    "rebalance": {"frequency": "biweekly"},
    "entry_rules": [{"field": "case_score", "operator": "gte", "value": 70}],
    "exit_rules": [], "regime_rules": [],
}

portfolio_config = {
    "name": "Multi-Strategy Alpha",
    "portfolio_type": "multi_strategy",
    "allocation_method": "equal",
    "strategies": [
        {"strategy_name": "Momentum Quality", "strategy_config": momentum_config},
        {"strategy_name": "Value Contrarian", "strategy_config": value_config},
        {"strategy_name": "Quality Growth", "strategy_config": quality_config},
    ],
    "constraints": {
        "max_single_strategy_weight": 0.50,
        "min_strategy_weight": 0.05,
        "max_strategy_correlation": 0.85,
    },
}


# ── Tests ──

def test_imports():
    from src.engines.strategy_portfolio import (
        StrategyPortfolioEngine, PortfolioMonitor,
        PortfolioType, StrategyPortfolio, PortfolioConstraints,
    )

test("Imports", test_imports)


from src.engines.strategy_portfolio.engine import StrategyPortfolioEngine
from src.engines.strategy_portfolio.monitor import PortfolioMonitor


def test_portfolio_simulation():
    result = StrategyPortfolioEngine.run(
        portfolio_config=portfolio_config, data=data,
        initial_capital=1_000_000.0, use_full_cost_model=False,
    )
    assert "error" not in result, f"Error: {result.get('error')}"
    assert result["portfolio_id"], "No portfolio_id"
    assert result["trading_days"] > 0
    assert len(result["equity_curve"]) > 0
    assert result["final_value"] > 0
    assert len(result["strategies"]) == 3
    assert len(result["weights"]) == 3

test("Portfolio simulation (3 strategies)", test_portfolio_simulation)


def test_allocation_weights():
    result = StrategyPortfolioEngine.run(portfolio_config, data, use_full_cost_model=False)
    weights = result["weights"]
    total = sum(weights.values())
    assert 0.99 < total < 1.01, f"Weights don't sum to 1: {total}"
    for name, w in weights.items():
        assert 0.3 < w < 0.4, f"Equal weight expected ~0.33, got {w} for {name}"

test("Equal weight allocation", test_allocation_weights)


def test_risk_parity_allocation():
    rp_config = dict(portfolio_config)
    rp_config["allocation_method"] = "risk_parity"
    result = StrategyPortfolioEngine.run(rp_config, data, use_full_cost_model=False)
    weights = result["weights"]
    total = sum(weights.values())
    assert 0.99 < total < 1.01, f"Weights don't sum to 1: {total}"

test("Risk parity allocation", test_risk_parity_allocation)


def test_mean_variance_allocation():
    mv_config = dict(portfolio_config)
    mv_config["allocation_method"] = "mean_variance"
    result = StrategyPortfolioEngine.run(mv_config, data, use_full_cost_model=False)
    weights = result["weights"]
    assert len(weights) > 0

test("Mean-variance allocation", test_mean_variance_allocation)


def test_sharpe_optimal_allocation():
    so_config = dict(portfolio_config)
    so_config["allocation_method"] = "sharpe_optimal"
    result = StrategyPortfolioEngine.run(so_config, data, use_full_cost_model=False)
    weights = result["weights"]
    assert len(weights) > 0

test("Sharpe-optimal allocation", test_sharpe_optimal_allocation)


def test_regime_adaptive_allocation():
    ra_config = dict(portfolio_config)
    ra_config["allocation_method"] = "regime_adaptive"
    result = StrategyPortfolioEngine.run(ra_config, data, use_full_cost_model=False)
    weights = result["weights"]
    assert len(weights) > 0

test("Regime-adaptive allocation", test_regime_adaptive_allocation)


def test_strategy_contribution():
    result = StrategyPortfolioEngine.run(portfolio_config, data, use_full_cost_model=False)
    contrib = result["strategy_contribution"]
    assert len(contrib) == 3
    for c in contrib:
        assert "strategy_name" in c
        assert "weight" in c
        assert "strategy_return" in c
        assert "weighted_return" in c
        assert "contribution_pct" in c

test("Strategy contribution analysis", test_strategy_contribution)


def test_diversification():
    result = StrategyPortfolioEngine.run(portfolio_config, data, use_full_cost_model=False)
    div = result["diversification"]
    assert "correlation_matrix" in div
    assert "diversification_ratio" in div
    assert "position_overlap" in div
    assert "concentration_index" in div
    assert "max_correlation" in div
    assert "verdict" in div

    assert div["diversification_ratio"] > 0
    assert div["concentration_index"] > 0
    assert div["verdict"] in ["well_diversified", "moderately_diversified", "concentrated", "single_strategy"]

test("Diversification analysis (corr/overlap/HHI/DR)", test_diversification)


def test_merged_positions():
    result = StrategyPortfolioEngine.run(portfolio_config, data, use_full_cost_model=False)
    positions = result["merged_positions"]
    assert len(positions) > 0
    for p in positions:
        assert "ticker" in p
        assert "weight" in p
        assert "sources" in p
        assert "source_count" in p

test("Merged positions with source tracking", test_merged_positions)


def test_regime_analysis():
    result = StrategyPortfolioEngine.run(portfolio_config, data, use_full_cost_model=False)
    ra = result["regime_analysis"]
    assert "regimes" in ra
    assert ra["regime_count"] >= 2

test("Portfolio regime analysis", test_regime_analysis)


def test_portfolio_monitor():
    result = StrategyPortfolioEngine.run(portfolio_config, data, use_full_cost_model=False)
    monitor = PortfolioMonitor.check(result)
    assert "health_status" in monitor
    assert "current_composition" in monitor
    assert "alerts" in monitor
    assert "regime_alignment" in monitor
    assert len(monitor["current_composition"]) == 3
    assert monitor["health_status"] in ["healthy", "warning", "critical"]

test("Portfolio monitoring & alerts", test_portfolio_monitor)


def test_portfolio_metrics():
    result = StrategyPortfolioEngine.run(portfolio_config, data, use_full_cost_model=False)
    m = result["metrics"]
    for key in ["cagr", "sharpe_ratio", "sortino_ratio", "max_drawdown",
                "diversification_ratio", "concentration_index", "strategy_count"]:
        assert key in m, f"Missing metric: {key}"

test("Portfolio metrics (16 metrics)", test_portfolio_metrics)


# Summary
print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
print("=" * 60)
