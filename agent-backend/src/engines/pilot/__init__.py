"""
src/engines/pilot/__init__.py
─────────────────────────────────────────────────────────────────────────────
365 Advisers Pilot Deployment engine.

Provides the infrastructure for running a time-bounded pilot that
validates signal quality, idea generation, strategy performance,
and portfolio construction before broader production launch.
"""

from .alerts import PilotAlertEvaluator
from .config import (
    PILOT_DURATION_WEEKS,
    PILOT_INITIAL_CAPITAL,
    PILOT_STRATEGY_CONFIGS,
    PILOT_TICKERS,
    PILOT_UNIVERSE,
    AlertThresholds,
    MetricTargets,
    get_all_portfolio_configs,
    get_benchmark_portfolio_config,
    get_research_portfolio_config,
    get_strategy_portfolio_config,
)
from .metrics import PilotMetrics
from .models import (
    PilotAlert,
    PilotAlertSeverity,
    PilotAlertType,
    PilotDailySnapshot,
    PilotDashboardData,
    PilotHealthStatus,
    PilotPhase,
    PilotPortfolioMetrics,
    PilotSignalMetrics,
    PilotStatus,
    PilotStrategyMetrics,
    PilotSuccessAssessment,
    PilotWeeklyReport,
    PortfolioType,
)
from .runner import PilotRunner

__all__ = [
    # Runner
    "PilotRunner",
    # Alerts
    "PilotAlertEvaluator",
    # Metrics
    "PilotMetrics",
    # Config
    "PILOT_DURATION_WEEKS",
    "PILOT_INITIAL_CAPITAL",
    "PILOT_STRATEGY_CONFIGS",
    "PILOT_TICKERS",
    "PILOT_UNIVERSE",
    "AlertThresholds",
    "MetricTargets",
    "get_all_portfolio_configs",
    "get_benchmark_portfolio_config",
    "get_research_portfolio_config",
    "get_strategy_portfolio_config",
    # Models
    "PilotAlert",
    "PilotAlertSeverity",
    "PilotAlertType",
    "PilotDailySnapshot",
    "PilotDashboardData",
    "PilotHealthStatus",
    "PilotPhase",
    "PilotPortfolioMetrics",
    "PilotSignalMetrics",
    "PilotStatus",
    "PilotStrategyMetrics",
    "PilotSuccessAssessment",
    "PilotWeeklyReport",
    "PortfolioType",
]
