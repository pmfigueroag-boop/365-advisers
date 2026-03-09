"""
src/engines/autonomous_pm/
──────────────────────────────────────────────────────────────────────────────
Autonomous Portfolio Manager (APM) — AI-Driven Portfolio Management.

Constructs, allocates, rebalances, monitors, and evaluates portfolios
autonomously using Investment Brain signals and quantitative methods.
"""

from src.engines.autonomous_pm.engine import AutonomousPortfolioManager
from src.engines.autonomous_pm.models import (
    APMDashboard,
    APMPortfolio,
    APMPosition,
    AllocationMethodAPM,
    PerformanceSnapshot,
    PortfolioObjective,
    PortfolioRiskReport,
    RebalanceRecommendation,
    RebalanceTrigger,
    RiskViolation,
)

__all__ = [
    "AutonomousPortfolioManager",
    "APMDashboard",
    "APMPortfolio",
    "APMPosition",
    "AllocationMethodAPM",
    "PerformanceSnapshot",
    "PortfolioObjective",
    "PortfolioRiskReport",
    "RebalanceRecommendation",
    "RebalanceTrigger",
    "RiskViolation",
]
