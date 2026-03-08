"""
src/engines/strategy_backtest/__init__.py
─────────────────────────────────────────────────────────────────────────────
Strategy Backtesting Framework — evaluate strategies with realistic costs.
"""

from .engine import StrategyBacktester
from .full_engine import StrategyBacktestEngine
from .metrics import StrategyMetrics
from .benchmark import BenchmarkComparison
from .regime_analysis import RegimePerformance
from .walk_forward_strategy import WalkForwardStrategyValidator
from .report import BacktestReport
from .comparator import StrategyComparator
from .models import BacktestDataBundle, TradeRecord, PositionSnapshot, EquityCurvePoint, CostBreakdown

__all__ = [
    # Legacy
    "StrategyBacktester",
    # New 8-stage engine
    "StrategyBacktestEngine",
    # Analytics
    "StrategyMetrics",
    "BenchmarkComparison",
    "RegimePerformance",
    "WalkForwardStrategyValidator",
    "BacktestReport",
    "StrategyComparator",
    # Models
    "BacktestDataBundle",
    "TradeRecord",
    "PositionSnapshot",
    "EquityCurvePoint",
    "CostBreakdown",
]
