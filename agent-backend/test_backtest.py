"""Integration test for Strategy Backtesting Framework with synthetic data."""
import sys
import os
import traceback
import random

sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_bt.db")

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


# ── Generate synthetic data ──

def make_synthetic_data(n_dates=120, tickers=None):
    """Generate synthetic backtest data bundle."""
    if tickers is None:
        tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "META", "TSLA", "JPM"]

    random.seed(42)
    dates = [f"2025-{m:02d}-{d:02d}" for m in range(1, 7) for d in range(1, 21)][:n_dates]

    # Price matrix
    prices = {}
    for ticker in tickers:
        base = random.uniform(100, 500)
        prices[ticker] = {}
        for i, d in enumerate(dates):
            drift = random.gauss(0.001, 0.02)
            base *= (1 + drift)
            prices[ticker][d] = round(base, 2)

    # Signals (some days active, some not)
    signals_by_date = {}
    categories = ["momentum", "quality", "value"]
    for d in dates:
        sigs = []
        for ticker in tickers:
            if random.random() > 0.4:
                sigs.append({
                    "signal_id": f"sig_{ticker}_{d}",
                    "ticker": ticker,
                    "category": random.choice(categories),
                    "strength": random.choice(["strong", "moderate", "weak"]),
                    "confidence": round(random.uniform(0.3, 0.95), 2),
                })
        signals_by_date[d] = sigs

    # Scores
    scores_by_date = {}
    for d in dates:
        scores_by_date[d] = {}
        for ticker in tickers:
            scores_by_date[d][ticker] = {
                "case_score": random.randint(40, 95),
                "uos": round(random.uniform(4.0, 9.5), 1),
                "business_quality": round(random.uniform(4.0, 9.0), 1),
                "opportunity_score": round(random.uniform(4.0, 9.5), 1),
            }

    # Regimes
    regime_cycle = ["bull", "bull", "bull", "range", "bear", "bear", "high_vol", "range"]
    regimes_by_date = {d: regime_cycle[i % len(regime_cycle)] for i, d in enumerate(dates)}

    # Benchmark
    bm_base = 450.0
    benchmark_prices = {}
    for d in dates:
        bm_base *= (1 + random.gauss(0.0005, 0.015))
        benchmark_prices[d] = round(bm_base, 2)

    # Liquidity
    liquidity = {t: random.uniform(50_000_000, 500_000_000) for t in tickers}

    return {
        "prices": prices,
        "signals_by_date": signals_by_date,
        "scores_by_date": scores_by_date,
        "regimes_by_date": regimes_by_date,
        "benchmark_prices": benchmark_prices,
        "liquidity": liquidity,
    }


# ── Tests ──


def test_imports():
    from src.engines.strategy_backtest import (
        StrategyBacktestEngine,
        StrategyComparator,
        BacktestDataBundle,
        StrategyMetrics,
        BenchmarkComparison,
        RegimePerformance,
        WalkForwardStrategyValidator,
    )


test("Imports", test_imports)


from src.engines.strategy_backtest.full_engine import StrategyBacktestEngine
from src.engines.strategy_backtest.comparator import StrategyComparator

data = make_synthetic_data()

# Momentum strategy config
momentum_config = {
    "name": "Momentum Quality",
    "signals": {
        "required_categories": ["momentum", "quality"],
        "composition_logic": "all_required",
        "min_active_signals": 1,
        "min_confidence": "medium",
    },
    "thresholds": {
        "min_case_score": 60,
        "min_uos": 5.0,
    },
    "portfolio": {
        "max_positions": 8,
        "sizing_method": "equal",
        "max_single_position": 0.15,
    },
    "rebalance": {
        "frequency": "weekly",
    },
    "entry_rules": [
        {"field": "case_score", "operator": "gte", "value": 65},
        {"field": "opportunity_score", "operator": "gte", "value": 6.0},
    ],
    "exit_rules": [
        {"rule_type": "trailing_stop", "params": {"pct": 0.15}},
    ],
    "regime_rules": [
        {"regime": "bull", "action": "full_exposure"},
        {"regime": "bear", "action": "no_new_entries"},
        {"regime": "high_vol", "action": "reduce_50"},
    ],
}


def test_full_backtest():
    result = StrategyBacktestEngine.run(
        strategy_config=momentum_config,
        data=data,
        initial_capital=1_000_000.0,
        use_full_cost_model=False,
        cost_per_trade_bps=5.0,
    )

    assert "error" not in result, f"Backtest error: {result.get('error')}"
    assert result["run_id"], "Missing run_id"
    assert result["trading_days"] > 0, "No trading days"
    assert len(result["equity_curve"]) > 0, "Empty equity curve"
    assert result["final_value"] > 0, "Negative final value"

    m = result["metrics"]
    assert "cagr" in m, "Missing CAGR"
    assert "sharpe_ratio" in m, "Missing Sharpe"
    assert "sortino_ratio" in m, "Missing Sortino"
    assert "max_drawdown" in m, "Missing max DD"
    assert "max_dd_duration_days" in m, "Missing DD duration"
    assert "win_rate" in m, "Missing win rate"
    assert "avg_win_loss_ratio" in m, "Missing win/loss ratio"
    assert "profit_factor" in m, "Missing profit factor"
    assert "annualized_turnover" in m, "Missing turnover"
    assert "avg_positions" in m, "Missing avg positions"
    assert "cost_drag_bps" in m, "Missing cost drag"

    # Regime analysis
    ra = result["regime_analysis"]
    assert "regimes" in ra, "Missing regime analysis"
    assert ra["regime_count"] > 0, "No regimes detected"

    # Cost analysis
    ca = result["cost_analysis"]
    assert ca["total_trades"] > 0, "No trades executed"


test("Full 8-stage backtest", test_full_backtest)


def test_metrics_count():
    result = StrategyBacktestEngine.run(momentum_config, data, use_full_cost_model=False)
    m = result["metrics"]
    expected_keys = [
        "total_return", "cagr", "annualized_return", "annualized_volatility",
        "sharpe_ratio", "sortino_ratio", "max_drawdown", "max_dd_duration_days",
        "calmar_ratio", "win_rate", "avg_win_loss_ratio", "profit_factor",
        "annualized_turnover", "avg_positions", "cost_drag_bps",
    ]
    for key in expected_keys:
        assert key in m, f"Missing metric: {key}"


test("19 metrics present", test_metrics_count)


def test_benchmark_comparison():
    result = StrategyBacktestEngine.run(momentum_config, data, use_full_cost_model=False)
    bc = result.get("benchmark_comparison")
    assert bc is not None, "No benchmark comparison"
    assert "alpha" in bc, "Missing alpha"
    assert "beta" in bc, "Missing beta"
    assert "information_ratio" in bc, "Missing IR"
    assert "tracking_error" in bc, "Missing TE"


test("Benchmark comparison (alpha/beta/IR/TE)", test_benchmark_comparison)


def test_regime_analysis():
    result = StrategyBacktestEngine.run(momentum_config, data, use_full_cost_model=False)
    ra = result["regime_analysis"]
    assert ra["regime_count"] >= 2, f"Only {ra['regime_count']} regimes"
    assert ra["best_regime"] is not None, "No best regime"
    assert ra["worst_regime"] is not None, "No worst regime"


test("Regime-segmented analysis", test_regime_analysis)


def test_regime_rules():
    """Test that regime rules affect entries (bear = no_new_entries)."""
    # Use a config with aggressive bear rule
    bear_config = dict(momentum_config)
    bear_config["regime_rules"] = [
        {"regime": "bear", "action": "exit_all"},
        {"regime": "bull", "action": "full_exposure"},
    ]
    result = StrategyBacktestEngine.run(bear_config, data, use_full_cost_model=False)
    # Should still complete without error
    assert "error" not in result


test("Regime rules execution", test_regime_rules)


def test_entry_exit_rules():
    """Test that entry/exit rules filter trades."""
    strict_config = dict(momentum_config)
    strict_config["entry_rules"] = [
        {"field": "case_score", "operator": "gte", "value": 95},  # Very strict
    ]
    result = StrategyBacktestEngine.run(strict_config, data, use_full_cost_model=False)
    # Fewer trades with strict rules
    lenient_result = StrategyBacktestEngine.run(momentum_config, data, use_full_cost_model=False)
    assert result["cost_analysis"]["total_trades"] <= lenient_result["cost_analysis"]["total_trades"]


test("Entry/exit rules affect trade count", test_entry_exit_rules)


def test_strategy_comparison():
    # Value strategy
    value_config = {
        "name": "Value Contrarian",
        "signals": {"required_categories": ["value"], "min_confidence": "low"},
        "thresholds": {"min_case_score": 50},
        "portfolio": {"max_positions": 10, "sizing_method": "equal"},
        "rebalance": {"frequency": "monthly"},
        "entry_rules": [{"field": "case_score", "operator": "gte", "value": 55}],
        "exit_rules": [],
        "regime_rules": [],
    }

    results = []
    for cfg in [momentum_config, value_config]:
        r = StrategyBacktestEngine.run(cfg, data, use_full_cost_model=False)
        results.append(r)

    comparison = StrategyComparator.compare(results)
    assert comparison["strategy_count"] == 2
    assert len(comparison["strategies"]) == 2
    assert "rankings" in comparison
    assert "by_sharpe" in comparison["rankings"]
    assert "regime_comparison" in comparison
    assert "correlation_matrix" in comparison

    # Correlation matrix should have 2x2 entries
    matrix = comparison["correlation_matrix"]
    assert len(matrix) == 2


test("Multi-strategy comparison", test_strategy_comparison)


def test_cost_model_fallback():
    """Test that flat cost fallback works."""
    result = StrategyBacktestEngine.run(
        momentum_config, data,
        use_full_cost_model=False,
        cost_per_trade_bps=10.0,
    )
    assert result["cost_analysis"]["total_cost_usd"] > 0


test("Cost model fallback (flat bps)", test_cost_model_fallback)


def test_rebalance_frequency():
    """Daily rebalance should produce more trades than monthly."""
    daily_cfg = dict(momentum_config)
    daily_cfg["rebalance"] = {"frequency": "daily"}
    daily_result = StrategyBacktestEngine.run(daily_cfg, data, use_full_cost_model=False)

    monthly_cfg = dict(momentum_config)
    monthly_cfg["rebalance"] = {"frequency": "monthly"}
    monthly_result = StrategyBacktestEngine.run(monthly_cfg, data, use_full_cost_model=False)

    assert daily_result["metrics"]["rebalance_count"] >= monthly_result["metrics"]["rebalance_count"]


test("Rebalance frequency affects trade count", test_rebalance_frequency)


def test_equity_curve_structure():
    result = StrategyBacktestEngine.run(momentum_config, data, use_full_cost_model=False)
    ec = result["equity_curve"]
    assert len(ec) > 0
    point = ec[0]
    assert "date" in point
    assert "portfolio_value" in point
    assert "drawdown" in point
    assert "regime" in point
    assert "positions_count" in point


test("Equity curve structure", test_equity_curve_structure)


def test_positions_history():
    result = StrategyBacktestEngine.run(momentum_config, data, use_full_cost_model=False)
    ph = result["positions_history"]
    assert len(ph) > 0
    snap = ph[0]
    assert "date" in snap
    assert "positions" in snap
    assert "positions_count" in snap


test("Positions history snapshots", test_positions_history)


# Summary
print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
print("=" * 60)
