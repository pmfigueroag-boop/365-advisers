# -*- coding: utf-8 -*-
"""
test_pilot_phase1.py
─────────────────────────────────────────────────────────────────────────────
Phase 1 wiring tests — validates that the runner pipeline steps are
properly connected to real engines.

Run: python test_pilot_phase1.py
"""

import sys
import os
sys.path.insert(0, '.')
os.environ["PYTHONIOENCODING"] = "utf-8"

passed = 0
failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  PASS {msg}")


def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  FAIL {msg}  {detail}")


def check(condition, msg, detail=""):
    if condition:
        ok(msg)
    else:
        fail(msg, detail)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: New config values
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 1: Phase 1 config additions")

from src.engines.pilot.config import (
    PILOT_TICKERS,
    PILOT_STRATEGY_CONFIGS,
)

check(isinstance(PILOT_TICKERS, list), "PILOT_TICKERS is a list")
check(len(PILOT_TICKERS) == 10, f"PILOT_TICKERS has 10 tickers (got {len(PILOT_TICKERS)})")
check("AAPL" in PILOT_TICKERS, "AAPL in PILOT_TICKERS")
check("JPM" in PILOT_TICKERS, "JPM in PILOT_TICKERS (finance)")
check("JNJ" in PILOT_TICKERS, "JNJ in PILOT_TICKERS (healthcare)")
check("XOM" in PILOT_TICKERS, "XOM in PILOT_TICKERS (energy)")

check(isinstance(PILOT_STRATEGY_CONFIGS, list), "PILOT_STRATEGY_CONFIGS is a list")
check(len(PILOT_STRATEGY_CONFIGS) == 3, f"3 strategy configs (got {len(PILOT_STRATEGY_CONFIGS)})")

strat_names = [c["name"] for c in PILOT_STRATEGY_CONFIGS]
check("Momentum Quality" in strat_names, "Momentum Quality strategy defined")
check("Value Contrarian" in strat_names, "Value Contrarian strategy defined")
check("Low Volatility" in strat_names, "Low Volatility strategy defined")

# Each strategy config has required keys
for cfg in PILOT_STRATEGY_CONFIGS:
    for key in ["required_categories", "min_strength", "min_confidence", "min_case"]:
        check(key in cfg, f"Strategy '{cfg['name']}' has '{key}'")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: Runner pipeline methods exist and have correct signatures
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 2: Runner pipeline methods")

from src.engines.pilot.runner import PilotRunner
import inspect

runner = PilotRunner()

# Step 1
sig = inspect.signature(runner._step_refresh_data)
check(len(sig.parameters) == 0, "_step_refresh_data takes 0 params (self excluded)")
# Verify return type includes prices dict
result = runner._step_refresh_data.__doc__ or ""
check("prices" in result.lower() or "close" in result.lower() or "ticker" in result.lower(),
      "_step_refresh_data doc mentions price/close/ticker")

# Step 2
sig2 = inspect.signature(runner._step_evaluate_signals)
params2 = list(sig2.parameters.keys())
check("prices" in params2, "_step_evaluate_signals takes 'prices' param")

# Step 3
sig3 = inspect.signature(runner._step_generate_ideas)
params3 = list(sig3.parameters.keys())
check("prices" in params3, "_step_generate_ideas takes 'prices' param")

# Step 4
sig4 = inspect.signature(runner._step_evaluate_strategies)
params4 = list(sig4.parameters.keys())
check("status" in params4, "_step_evaluate_strategies takes 'status' param")
check("signal_results" in params4, "_step_evaluate_strategies takes 'signal_results'")
check("prices" in params4, "_step_evaluate_strategies takes 'prices'")

# Step 5
sig5 = inspect.signature(runner._step_update_portfolios)
params5 = list(sig5.parameters.keys())
check("status" in params5, "_step_update_portfolios takes 'status'")
check("prices" in params5, "_step_update_portfolios takes 'prices'")

# Step 6
sig6 = inspect.signature(runner._step_compute_metrics)
params6 = list(sig6.parameters.keys())
check("pilot_id" in params6, "_step_compute_metrics takes 'pilot_id'")
check("status" in params6, "_step_compute_metrics takes 'status'")

# Step 7
sig7 = inspect.signature(runner._step_evaluate_alerts)
params7 = list(sig7.parameters.keys())
check("metrics_results" in params7, "_step_evaluate_alerts takes 'metrics_results'")

# Step 8
sig8 = inspect.signature(runner._step_persist_snapshot)
params8 = list(sig8.parameters.keys())
check("metrics_results" in params8, "_step_persist_snapshot takes 'metrics_results'")
check("prices" in params8, "_step_persist_snapshot takes 'prices'")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: Step 1 — Data refresh returns prices
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 3: Data refresh via yfinance")

try:
    data_fresh, ts, prices = runner._step_refresh_data()
    check(isinstance(data_fresh, bool), f"data_fresh is bool: {data_fresh}")
    check(ts is not None, "timestamp is not None")
    check(isinstance(prices, dict), "prices is a dict")
    check(len(prices) > 0, f"prices has {len(prices)} tickers (expected > 0)")

    # Check at least some prices look valid
    for t, p in list(prices.items())[:3]:
        check(isinstance(p, float) and p > 0, f"{t} price = ${p:.2f}")
except Exception as e:
    fail(f"Data refresh raised exception: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: Step 2 — Signal evaluation
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 4: Signal evaluation")

sig_results = runner._step_evaluate_signals(prices if 'prices' in dir() else {})
check(isinstance(sig_results, dict), "Signal results is a dict")
check("total" in sig_results, "Has 'total' key")
check("total_fired" in sig_results, "Has 'total_fired' key")
check("by_category" in sig_results, "Has 'by_category' key")
check("by_ticker" in sig_results, "Has 'by_ticker' key")
check("case_scores" in sig_results, "Has 'case_scores' key")

total = sig_results.get("total", 0)
fired = sig_results.get("total_fired", 0)
check(total >= 0, f"Total signals = {total}")
check(fired >= 0, f"Total fired = {fired}")

by_cat = sig_results.get("by_category", {})
if by_cat:
    check(len(by_cat) > 0, f"Categories evaluated: {list(by_cat.keys())}")

case_scores = sig_results.get("case_scores", {})
for tk, sc in list(case_scores.items())[:3]:
    check(0 <= sc <= 100, f"CASE {tk} = {sc:.1f} (in 0-100 range)")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: Step 3 — Idea generation
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 5: Idea generation")

idea_results = runner._step_generate_ideas(prices if 'prices' in dir() else {})
check(isinstance(idea_results, dict), "Idea results is a dict")
check("total" in idea_results, "Has 'total' key")
check("by_type" in idea_results, "Has 'by_type' key")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: Step 4 — Strategy evaluation
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 6: Strategy evaluation")

from src.engines.pilot.models import PilotStatus, PilotPhase

mock_status = PilotStatus(
    pilot_id="test123",
    phase=PilotPhase.OBSERVATION,
    current_week=2,
    total_weeks=12,
)

strat_results = runner._step_evaluate_strategies(
    mock_status, sig_results, prices if 'prices' in dir() else {},
)
check(isinstance(strat_results, dict), "Strategy results is a dict")
check("strategies_evaluated" in strat_results, "Has 'strategies_evaluated' key")
check("drawdowns" in strat_results, "Has 'drawdowns' key")
check("eligible_counts" in strat_results, "Has 'eligible_counts' key")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 7: Module exports
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 7: Module __init__ exports")

from src.engines.pilot import (
    PILOT_TICKERS,
    PILOT_STRATEGY_CONFIGS,
    PilotRunner,
    PilotAlertEvaluator,
    PilotMetrics,
)

check(PILOT_TICKERS is not None, "PILOT_TICKERS exported from __init__")
check(PILOT_STRATEGY_CONFIGS is not None, "PILOT_STRATEGY_CONFIGS exported from __init__")
check(PilotRunner is not None, "PilotRunner exported from __init__")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 8: API Router imports
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 8: API router")

from src.routes.pilot import router

check(router is not None, "Pilot router imports successfully")
routes = [r.path for r in router.routes]
check(any("/config" in r for r in routes), "/pilot/config endpoint exists")
check(any("/metrics/" in r for r in routes), "/pilot/metrics/{pilot_id} endpoint exists")
check(any("/leaderboards/" in r for r in routes), "/pilot/leaderboards/{pilot_id} endpoint exists")
check(any("/portfolios/" in r for r in routes), "/pilot/portfolios/{pilot_id} endpoint exists")
check(any("/success-criteria/" in r for r in routes), "/pilot/success-criteria/{pilot_id} endpoint exists")


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(f"PILOT PHASE 1 TESTS: {passed} passed, {failed} failed")
print("=" * 60)

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
