"""
src/engines/strategy/
─────────────────────────────────────────────────────────────────────────────
Strategy Definition Framework — declarative strategy models, registry,
composition, and lifecycle management.
"""

from .definition import (
    StrategyDefinition,
    StrategyConfig,
    StrategyCreate,
    StrategySummary,
    EntryRule,
    ExitRule,
    RegimeAction,
    UniverseConfig,
    StrategyMetadata,
    SignalComposition,
    ScoreThresholds,
    PortfolioRules,
    RebalanceConfig,
    LifecycleState,
    StrategyCategory,
    load_strategy_yaml,
    save_strategy_yaml,
    load_all_strategies_from_dir,
)
from .registry import StrategyRegistry
from .composer import StrategyComposer
from .filter import StrategyFilter
from .evaluator import StrategyEvaluator

__all__ = [
    # Core
    "StrategyDefinition",
    "StrategyConfig",
    "StrategyCreate",
    "StrategySummary",
    # Sub-models
    "EntryRule",
    "ExitRule",
    "RegimeAction",
    "UniverseConfig",
    "StrategyMetadata",
    "SignalComposition",
    "ScoreThresholds",
    "PortfolioRules",
    "RebalanceConfig",
    # Enums
    "LifecycleState",
    "StrategyCategory",
    # Operations
    "StrategyRegistry",
    "StrategyComposer",
    "StrategyFilter",
    "StrategyEvaluator",
    # YAML
    "load_strategy_yaml",
    "save_strategy_yaml",
    "load_all_strategies_from_dir",
]
