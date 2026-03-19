"""
test_pilot.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive test script for the Pilot Deployment system.

Tests:
  1. Model imports and instantiation
  2. Config defaults and portfolio configs
  3. Alert evaluator (all 9 alert types)
  4. Metrics calculator (signal, strategy, portfolio, Go/No-Go)
  5. Runner initialization and lifecycle
"""

import sys
sys.path.insert(0, ".")

from datetime import datetime, timezone, timedelta

passed = 0
failed = 0


def test(name: str, condition: bool):
    global passed, failed
    if condition:
        print(f"  PASS {name}")
        passed += 1
    else:
        print(f"  FAIL {name}")
        failed += 1


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: Import all models
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 1: Import all pilot models")

try:
    from src.engines.pilot.models import (
        PilotPhase,
        PilotAlertType,
        PilotAlertSeverity,
        PortfolioType,
        MetricLevel,
        EntryExitCriteria,
        PilotPortfolioConfig,
        PilotStatus,
        PilotDailySnapshot,
        PilotAlert,
        PilotSignalMetrics,
        PilotIdeaMetrics,
        PilotStrategyMetrics,
        PilotPortfolioMetrics,
        PilotHealthStatus,
        SignalLeaderboardEntry,
        StrategyLeaderboardEntry,
        PilotWeeklyReport,
        SuccessCriterionResult,
        PilotSuccessAssessment,
        PilotDashboardData,
    )
    test("All 21 models imported", True)
except Exception as e:
    test(f"Import failed: {e}", False)

# Instantiate core models
try:
    status = PilotStatus(pilot_id="test123")
    test("PilotStatus instantiates", status.pilot_id == "test123")
    test("PilotStatus default phase", status.phase == PilotPhase.SETUP)
    test("PilotStatus default weeks", status.total_weeks == 12)

    alert = PilotAlert(
        pilot_id="test123",
        alert_type=PilotAlertType.SIGNAL_DEGRADATION,
        severity=PilotAlertSeverity.WARNING,
        title="Test alert",
    )
    test("PilotAlert instantiates", alert.alert_type == PilotAlertType.SIGNAL_DEGRADATION)
    test("PilotAlert has auto-generated id", len(alert.id) == 16)

    snapshot = PilotDailySnapshot(
        pilot_id="test123",
        portfolio_id="port123",
        portfolio_type=PortfolioType.RESEARCH,
        snapshot_date=datetime.now(timezone.utc),
    )
    test("PilotDailySnapshot instantiates", snapshot.nav == 1_000_000.0)

    health = PilotHealthStatus()
    test("PilotHealthStatus defaults", health.uptime_pct == 100.0)

    dashboard = PilotDashboardData(
        pilot_status=status,
    )
    test("PilotDashboardData instantiates", dashboard.pilot_status.pilot_id == "test123")
except Exception as e:
    test(f"Model instantiation failed: {e}", False)


# Enum completeness
test("PilotPhase has 5 values", len(PilotPhase) == 5)
test("PilotAlertType has 9 values", len(PilotAlertType) == 9)
test("PilotAlertSeverity has 3 values", len(PilotAlertSeverity) == 3)
test("PortfolioType has 3 values", len(PortfolioType) == 3)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: Config defaults and portfolio configs
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 2: Configuration and portfolio configs")

from src.engines.pilot.config import (
    PILOT_DURATION_WEEKS,
    PILOT_INITIAL_CAPITAL,
    PILOT_UNIVERSE,
    AlertThresholds,
    MetricTargets,
    get_research_portfolio_config,
    get_strategy_portfolio_config,
    get_benchmark_portfolio_config,
    get_all_portfolio_configs,
)

test("Pilot duration = 12 weeks", PILOT_DURATION_WEEKS == 12)
test("Pilot capital = $1M", PILOT_INITIAL_CAPITAL == 1_000_000.0)
test("Pilot universe = sp500", PILOT_UNIVERSE == "sp500")

# Alert thresholds
thresholds = AlertThresholds()
test("Signal HR warning = 45%", thresholds.SIGNAL_HR_WARNING == 0.45)
test("Strategy DD warning = 10%", thresholds.STRATEGY_DD_WARNING == 0.10)
test("Strategy DD critical = 15%", thresholds.STRATEGY_DD_CRITICAL == 0.15)
test("Portfolio vol warning = 25%", thresholds.PORTFOLIO_VOL_WARNING == 0.25)
test("Portfolio vol critical = 35%", thresholds.PORTFOLIO_VOL_CRITICAL == 0.35)
test("Data staleness = 2h", thresholds.DATA_STALENESS_HOURS == 2.0)
test("CASE expired ratio = 30%", thresholds.CASE_EXPIRED_RATIO == 0.30)
test("Correlation warning = 0.7", thresholds.CORRELATION_WARNING == 0.70)

# Metric targets
targets = MetricTargets()
test("Signal HR target = 53%", targets.SIGNAL_HIT_RATE == 0.53)
test("Strategy Sharpe target = 0.8", targets.STRATEGY_SHARPE == 0.8)
test("Min criteria for GO = 4", targets.MIN_CRITERIA_FOR_GO == 4)

# Portfolio configs
research = get_research_portfolio_config()
test("Research portfolio type", research.portfolio_type == PortfolioType.RESEARCH)
test("Research max positions = 20", research.max_positions == 20)
test("Research sizing = vol_parity", research.sizing_method == "vol_parity")
test("Research entry/exit criteria exist", research.entry_exit is not None)
test("Research min CASE = 65", research.entry_exit.min_case_score == 65.0)
test("Research trailing stop = 12%", research.entry_exit.trailing_stop_pct == 0.12)

strategy = get_strategy_portfolio_config()
test("Strategy portfolio type", strategy.portfolio_type == PortfolioType.STRATEGY)
test("Strategy max positions = 30", strategy.max_positions == 30)
test("Strategy has 3 strategies", len(strategy.strategy_ids) == 3)
test("Strategy blend = risk_parity", strategy.blend_method == "risk_parity")

benchmark = get_benchmark_portfolio_config()
test("Benchmark portfolio type", benchmark.portfolio_type == PortfolioType.BENCHMARK)
test("Benchmark SPY weight = 70%", benchmark.benchmark_weights.get("SPY") == 0.70)
test("Benchmark QQQ weight = 30%", benchmark.benchmark_weights.get("QQQ") == 0.30)

all_configs = get_all_portfolio_configs()
test("3 portfolio configs total", len(all_configs) == 3)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: Alert evaluator
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 3: Alert evaluator (9 alert types)")

from src.engines.pilot.alerts import PilotAlertEvaluator

evaluator = PilotAlertEvaluator("test_pilot")

# 3a: Signal degradation
alerts = evaluator._check_signal_degradation({"momentum": 0.40, "value": 0.60})
test("Signal degradation fires for momentum", len(alerts) == 1)
test("Signal degradation severity = WARNING", alerts[0].severity == PilotAlertSeverity.WARNING)
test("Signal degradation type correct", alerts[0].alert_type == PilotAlertType.SIGNAL_DEGRADATION)

# 3b: Strategy drawdown - warning
alerts = evaluator._check_strategy_drawdown({"mom_quality": -0.11})
test("Strategy DD warning fires at 11%", len(alerts) == 1)
test("Strategy DD warning severity", alerts[0].severity == PilotAlertSeverity.WARNING)

# 3c: Strategy drawdown - critical
alerts = evaluator._check_strategy_drawdown({"mom_quality": -0.18})
test("Strategy DD critical fires at 18%", len(alerts) == 1)
test("Strategy DD critical severity", alerts[0].severity == PilotAlertSeverity.CRITICAL)
test("Strategy DD critical auto-action", alerts[0].auto_action == "pause_strategy")

# 3d: Portfolio volatility - warning
alerts = evaluator._check_portfolio_volatility({"port1": 0.28})
test("Portfolio vol warning fires at 28%", len(alerts) == 1)
test("Portfolio vol warning severity", alerts[0].severity == PilotAlertSeverity.WARNING)

# 3e: Portfolio volatility - critical
alerts = evaluator._check_portfolio_volatility({"port1": 0.40})
test("Portfolio vol critical fires at 40%", len(alerts) == 1)
test("Portfolio vol critical severity", alerts[0].severity == PilotAlertSeverity.CRITICAL)
test("Portfolio vol critical action", alerts[0].auto_action == "emergency_derisk_50_cash")

# 3f: Data staleness
stale_time = datetime.now(timezone.utc) - timedelta(hours=3)
alerts = evaluator._check_data_staleness(stale_time)
test("Data staleness fires at 3h", len(alerts) == 1)
test("Data staleness action", alerts[0].auto_action == "skip_daily_run")

# No staleness when fresh
fresh_time = datetime.now(timezone.utc) - timedelta(minutes=30)
alerts = evaluator._check_data_staleness(fresh_time)
test("No staleness for 30min-old data", len(alerts) == 0)

# 3g: CASE collapse
alerts = evaluator._check_case_collapse(0.35)
test("CASE collapse fires at 35%", len(alerts) == 1)
alerts = evaluator._check_case_collapse(0.20)
test("No CASE collapse at 20%", len(alerts) == 0)

# 3h: Correlation spike
alerts = evaluator._check_correlation_spike({"port1": 0.75, "port2": 0.50})
test("Correlation spike fires for port1", len(alerts) == 1)
test("Correlation spike correct portfolio", alerts[0].portfolio_id == "port1")

# 3i: Regime change
alerts = evaluator._check_regime_change("bear", "bull")
test("Regime change fires bull→bear", len(alerts) == 1)
test("Regime change severity = INFO", alerts[0].severity == PilotAlertSeverity.INFO)
alerts = evaluator._check_regime_change("bull", "bull")
test("No regime change if same", len(alerts) == 0)

# Full evaluation
all_alerts = evaluator.evaluate_all(
    signal_hit_rates={"momentum": 0.40},
    strategy_drawdowns={"mom": -0.18},
    portfolio_volatilities={"port1": 0.40},
    data_last_updated=stale_time,
    case_expired_ratio=0.35,
    portfolio_correlations={"port1": 0.75},
    current_regime="bear",
    previous_regime="bull",
)
test("Full evaluation fires multiple alerts", len(all_alerts) >= 5)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: Metrics calculator
# ═══════════════════════════════════════════════════════════════════════════
print("\n>> TEST 4: Metrics calculator")

from src.engines.pilot.metrics import PilotMetrics

metrics = PilotMetrics()

# 4a: Strategy metrics
strategy_returns = {
    "mom_quality": [0.01, -0.005, 0.008, 0.012, -0.003, 0.007, 0.002, -0.001, 0.009, 0.004],
    "low_vol": [0.003, 0.002, 0.001, -0.001, 0.004, 0.002, -0.002, 0.003, 0.001, 0.002],
}
strat_metrics = metrics.compute_strategy_metrics(strategy_returns)
test("Strategy metrics computed for 2 strategies", len(strat_metrics) == 2)
test("Sharpe ratio is numeric", isinstance(strat_metrics[0].sharpe_ratio, float))
test("Max drawdown is non-negative", strat_metrics[0].max_drawdown >= 0)
test("Win rate between 0 and 1", 0 <= strat_metrics[0].win_rate <= 1)

# 4b: Portfolio metrics
portfolio_returns = {
    "research_port": [0.01, -0.005, 0.008, 0.012, -0.003],
    "strategy_port": [0.003, 0.002, 0.001, -0.001, 0.004],
}
benchmark_returns = [0.002, 0.001, 0.003, -0.002, 0.001]
port_metrics = metrics.compute_portfolio_metrics(portfolio_returns, benchmark_returns)
test("Portfolio metrics for 2 portfolios", len(port_metrics) == 2)
test("Alpha is numeric", isinstance(port_metrics[0].alpha_vs_benchmark, float))

# 4c: Health status
health = metrics.compute_health_status(
    pipeline_complete=True,
    data_fresh=True,
    data_last_updated=datetime.now(timezone.utc),
    active_strategies=3,
    target_strategies=3,
    critical_alerts=0,
    warning_alerts=1,
    run_duration_seconds=45.2,
)
test("Health pipeline complete", health.pipeline_status == "complete")
test("Health data fresh", health.data_fresh)
test("Health duration captured", health.last_run_duration_seconds == 45.2)

# 4d: Go/No-Go assessment
assessment = metrics.check_success_criteria(
    signal_hit_rate=0.55,
    research_alpha=0.02,
    strategy_sharpe=1.1,
    max_drawdown=0.08,
    strategy_quality=70,
    system_uptime=0.995,
    pilot_id="test",
)
test("Assessment has 6 criteria", assessment.criteria_total == 6)
test("All criteria passed", assessment.criteria_passed == 6)
test("Recommendation = GO", assessment.recommendation == "GO")

# Test NO_GO
assessment_bad = metrics.check_success_criteria(
    signal_hit_rate=0.40,
    research_alpha=-0.05,
    strategy_sharpe=0.3,
    max_drawdown=0.25,
    strategy_quality=40,
    system_uptime=0.95,
    pilot_id="test",
)
test("Bad assessment = 0 passed", assessment_bad.criteria_passed == 0)
test("Bad recommendation = NO_GO", assessment_bad.recommendation == "NO_GO")

# Test EXTEND (exactly 3 pass: signal HR, max DD, uptime)
assessment_mid = metrics.check_success_criteria(
    signal_hit_rate=0.55,
    research_alpha=-0.01,
    strategy_sharpe=0.5,
    max_drawdown=0.08,
    strategy_quality=40,
    system_uptime=0.995,
    pilot_id="test",
)
test("Mid assessment = 3 passed", assessment_mid.criteria_passed == 3)
test("Mid recommendation = EXTEND", assessment_mid.recommendation == "EXTEND")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: Database records import
# ═══════════════════════════════════════════════════════════════════════════
print("\n🧪 TEST 5: Database record classes")

try:
    from src.data.database import (
        PilotRunRecord,
        PilotDailySnapshotRecord,
        PilotAlertRecord,
        PilotMetricRecord,
    )
    test("PilotRunRecord imported", PilotRunRecord.__tablename__ == "pilot_runs")
    test("PilotDailySnapshotRecord imported", PilotDailySnapshotRecord.__tablename__ == "pilot_daily_snapshots")
    test("PilotAlertRecord imported", PilotAlertRecord.__tablename__ == "pilot_alerts")
    test("PilotMetricRecord imported", PilotMetricRecord.__tablename__ == "pilot_metrics")
except Exception as e:
    test(f"DB record import failed: {e}", False)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: Runner and init import
# ═══════════════════════════════════════════════════════════════════════════
print("\n🧪 TEST 6: Runner and module init")

try:
    from src.engines.pilot import (
        PilotRunner,
        PilotAlertEvaluator,
        PilotMetrics,
        PILOT_DURATION_WEEKS,
        PILOT_INITIAL_CAPITAL,
        PILOT_UNIVERSE,
        PilotPhase,
        PilotAlertType,
    )
    test("PilotRunner imported from __init__", True)
    test("PilotAlertEvaluator imported from __init__", True)
    test("PilotMetrics imported from __init__", True)

    runner = PilotRunner()
    test("PilotRunner instantiates", runner.metrics is not None)
except Exception as e:
    test(f"Runner import failed: {e}", False)


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"PILOT DEPLOYMENT TESTS: {passed} passed, {failed} failed")
print(f"{'='*60}")
if __name__ == "__main__":
    if failed > 0:
        sys.exit(1)
