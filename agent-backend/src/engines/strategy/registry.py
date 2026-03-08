"""
src/engines/strategy/registry.py
─────────────────────────────────────────────────────────────────────────────
StrategyRegistry — versioned strategy management with lifecycle tracking.

Extended with:
  - Lifecycle state machine (draft → research → ... → retired)
  - Category-based filtering
  - YAML import/export
  - 7-category predefined template library
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.data.database import SessionLocal
from .definition import (
    StrategyDefinition,
    StrategyConfig,
    StrategyCreate,
    StrategySummary,
    LifecycleState,
    load_strategy_yaml,
    save_strategy_yaml,
)

logger = logging.getLogger("365advisers.strategy.registry")

# Allowed lifecycle transitions
_LIFECYCLE_TRANSITIONS: dict[str, list[str]] = {
    "draft":      ["research"],
    "research":   ["backtested", "draft"],
    "backtested": ["validated", "draft"],
    "validated":  ["paper"],
    "paper":      ["live", "research"],
    "live":       ["paused", "retired"],
    "paused":     ["live", "retired"],
    "retired":    [],
}


class StrategyRegistry:
    """Extended registry with versioning, lifecycle, and templates."""

    def __init__(self):
        self._definition = StrategyDefinition()

    # ── Core CRUD ─────────────────────────────────────────────────────────

    def create_strategy(
        self,
        name: str,
        description: str = "",
        config: dict | None = None,
        version: str = "1.0.0",
    ) -> str:
        """Create a new strategy and return its ID."""
        cfg = StrategyConfig(**config) if config else StrategyConfig()
        payload = StrategyCreate(
            name=name, description=description, config=cfg, version=version,
        )
        return self._definition.create(payload)

    def get_strategy(self, strategy_id: str) -> dict | None:
        """Get strategy summary."""
        summary = self._definition.get(strategy_id)
        return summary.model_dump() if summary else None

    def list_strategies(
        self,
        active_only: bool = True,
        category: str | None = None,
        lifecycle_state: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """List strategies with optional filters."""
        summaries = self._definition.list_strategies(
            active_only=active_only,
            category=category,
            lifecycle_state=lifecycle_state,
            tags=tags,
        )
        return [s.model_dump() for s in summaries]

    def update_strategy(self, strategy_id: str, config: dict) -> bool:
        """Update strategy config (creates new version internally)."""
        cfg = StrategyConfig(**config)
        return self._definition.update(strategy_id, cfg)

    def clone_strategy(self, source_id: str, new_name: str) -> str | None:
        """Clone an existing strategy with a new name."""
        source = self._definition.get(source_id)
        if not source:
            return None

        payload = StrategyCreate(
            name=new_name,
            description=f"Cloned from {source.name} ({source_id})",
            config=StrategyConfig(**source.config),
        )
        new_id = self._definition.create(payload)
        logger.info("Strategy cloned: %s → %s (%s)", source_id, new_id, new_name)
        return new_id

    def deactivate(self, strategy_id: str) -> bool:
        """Deactivate a strategy."""
        return self._definition.deactivate(strategy_id)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def transition(self, strategy_id: str, target_state: str) -> dict:
        """Attempt a lifecycle state transition.

        Returns:
            {success: bool, from_state: str, to_state: str, error?: str}
        """
        current = self._definition.get(strategy_id)
        if not current:
            return {"success": False, "error": "Strategy not found"}

        from_state = current.lifecycle_state
        allowed = _LIFECYCLE_TRANSITIONS.get(from_state, [])

        if target_state not in allowed:
            return {
                "success": False,
                "from_state": from_state,
                "to_state": target_state,
                "error": f"Invalid transition: {from_state} → {target_state}. Allowed: {allowed}",
            }

        ok = self._definition.set_lifecycle_state(strategy_id, target_state)
        return {
            "success": ok,
            "from_state": from_state,
            "to_state": target_state,
        }

    # ── YAML Import/Export ────────────────────────────────────────────────

    def import_from_yaml(self, path: str | Path) -> str:
        """Import a strategy from a YAML file. Returns new strategy_id."""
        data = load_strategy_yaml(path)
        name = data.pop("name", Path(path).stem)
        description = data.pop("description", "")
        version = data.pop("version", "1.0.0")
        data.pop("_source_file", None)

        return self.create_strategy(
            name=name,
            description=description,
            config=data,
            version=version,
        )

    def export_to_yaml(self, strategy_id: str, path: str | Path) -> Path | None:
        """Export a strategy to a YAML file."""
        summary = self._definition.get(strategy_id)
        if not summary:
            return None

        config = StrategyConfig(**summary.config)
        return save_strategy_yaml(
            config, path,
            name=summary.name,
            description=summary.description,
            version=summary.version,
        )

    # ── Predefined Templates ──────────────────────────────────────────────

    def get_predefined(self) -> list[dict]:
        """Return predefined strategy templates across 7 categories."""
        return [
            # ── Momentum ──
            {
                "name": "Momentum Quality",
                "description": "Combines strong momentum signals with quality filters for trend-following with quality tilt",
                "config": {
                    "signals": {
                        "required_categories": ["momentum", "quality"],
                        "min_signal_strength": 2.0,
                        "min_confidence": "medium",
                        "composition_logic": "all_required",
                        "min_active_signals": 3,
                    },
                    "thresholds": {"min_case_score": 65, "min_uos": 5.0, "min_business_quality": 6.0},
                    "portfolio": {
                        "max_positions": 15, "sizing_method": "vol_parity",
                        "max_single_position": 0.08, "max_sector_exposure": 0.25,
                    },
                    "rebalance": {"frequency": "biweekly", "trigger_type": "calendar"},
                    "entry_rules": [
                        {"field": "case_score", "operator": "gte", "value": 75, "label": "CASE above 75"},
                        {"field": "regime", "operator": "in", "value": ["bull", "range"], "label": "Bull or range regime"},
                    ],
                    "exit_rules": [
                        {"rule_type": "trailing_stop", "params": {"pct": 0.12}},
                        {"rule_type": "signal_reversal", "params": {"signal_categories": ["momentum"]}},
                    ],
                    "regime_rules": [
                        {"regime": "bull", "action": "full_exposure"},
                        {"regime": "bear", "action": "no_new_entries"},
                    ],
                    "metadata": {"category": "momentum", "horizon": "medium", "benchmark": "SPY",
                                 "tags": ["momentum", "quality", "regime-aware"]},
                },
            },
            # ── Value ──
            {
                "name": "Value Contrarian",
                "description": "Deep value with mean reversion signals — patient, concentrated",
                "config": {
                    "signals": {
                        "required_categories": ["value"],
                        "min_signal_strength": 1.0,
                        "min_confidence": "low",
                        "composition_logic": "any_required",
                    },
                    "thresholds": {"min_case_score": 50, "min_uos": 4.0, "min_business_quality": 5.0},
                    "portfolio": {
                        "max_positions": 10, "sizing_method": "equal",
                        "max_single_position": 0.12, "max_sector_exposure": 0.30,
                    },
                    "rebalance": {"frequency": "monthly"},
                    "exit_rules": [
                        {"rule_type": "time_stop", "params": {"days": 180}},
                        {"rule_type": "target_reached", "params": {"return_pct": 0.40}},
                    ],
                    "metadata": {"category": "value", "horizon": "long", "benchmark": "IWD",
                                 "tags": ["value", "contrarian", "concentrated"]},
                },
            },
            # ── Quality ──
            {
                "name": "Quality Compounders",
                "description": "High-quality businesses with durable competitive advantages and consistent earnings growth",
                "config": {
                    "signals": {
                        "required_categories": ["quality"],
                        "preferred_signals": ["roic_expansion", "earnings_quality_beat"],
                        "min_signal_strength": 2.0,
                        "min_confidence": "medium",
                    },
                    "thresholds": {"min_case_score": 60, "min_business_quality": 7.0, "min_uos": 5.5},
                    "portfolio": {
                        "max_positions": 12, "sizing_method": "vol_parity",
                        "max_single_position": 0.10, "max_sector_exposure": 0.25,
                    },
                    "rebalance": {"frequency": "monthly"},
                    "exit_rules": [
                        {"rule_type": "trailing_stop", "params": {"pct": 0.15}},
                    ],
                    "metadata": {"category": "quality", "horizon": "long", "benchmark": "QUAL",
                                 "tags": ["quality", "compounders", "moat"]},
                },
            },
            # ── Low Volatility ──
            {
                "name": "Low Volatility",
                "description": "Targets low-volatility equities with stable earnings for downside protection",
                "config": {
                    "signals": {
                        "required_categories": ["volatility"],
                        "min_signal_strength": 1.0,
                        "composition_logic": "any_required",
                    },
                    "thresholds": {"min_case_score": 40, "min_business_quality": 5.0},
                    "portfolio": {
                        "max_positions": 25, "sizing_method": "vol_parity",
                        "max_single_position": 0.06, "max_sector_exposure": 0.20,
                    },
                    "rebalance": {"frequency": "monthly"},
                    "universe": {"min_market_cap": 10_000_000_000, "max_volatility": 0.25},
                    "metadata": {"category": "low_vol", "horizon": "long", "benchmark": "SPLV",
                                 "tags": ["low-vol", "defensive", "stable"]},
                },
            },
            # ── Event Driven ──
            {
                "name": "Event Driven",
                "description": "Trades around filing events, institutional flow, and geopolitical catalysts",
                "config": {
                    "signals": {
                        "required_categories": ["flow", "sentiment"],
                        "min_signal_strength": 2.0,
                        "min_confidence": "medium",
                    },
                    "thresholds": {"min_case_score": 55, "min_uos": 3.0},
                    "portfolio": {
                        "max_positions": 20, "sizing_method": "equal",
                        "max_single_position": 0.06, "max_sector_exposure": 0.20,
                    },
                    "rebalance": {"frequency": "daily"},
                    "exit_rules": [
                        {"rule_type": "time_stop", "params": {"days": 30}},
                        {"rule_type": "trailing_stop", "params": {"pct": 0.08}},
                    ],
                    "metadata": {"category": "event_driven", "horizon": "short", "benchmark": "SPY",
                                 "tags": ["event", "catalyst", "flow"]},
                },
            },
            # ── Thematic: AI Infrastructure ──
            {
                "name": "AI Infrastructure",
                "description": "Focused on AI/tech infrastructure with growth and technical momentum",
                "config": {
                    "signals": {
                        "required_categories": ["momentum"],
                        "preferred_signals": ["golden_cross", "macd_bullish_crossover"],
                        "min_signal_strength": 2.0,
                        "min_confidence": "medium",
                    },
                    "thresholds": {"min_case_score": 60, "min_uos": 5.0, "min_business_quality": 7.0},
                    "portfolio": {
                        "max_positions": 12, "sizing_method": "rank_weighted",
                        "max_single_position": 0.10, "max_sector_exposure": 0.40,
                    },
                    "rebalance": {"frequency": "monthly"},
                    "universe": {"sector_filter": ["technology", "communication_services"]},
                    "metadata": {"category": "thematic", "horizon": "medium", "benchmark": "QQQ",
                                 "tags": ["AI", "tech", "infrastructure", "growth"]},
                },
            },
            # ── Multi-Factor ──
            {
                "name": "Balanced Multi-Factor",
                "description": "Diversified multi-factor approach combining value, momentum, and quality signals",
                "config": {
                    "signals": {
                        "required_categories": ["value", "momentum", "quality"],
                        "min_signal_strength": 1.5,
                        "min_confidence": "medium",
                        "composition_logic": "any_required",
                        "min_active_signals": 2,
                    },
                    "thresholds": {"min_case_score": 55, "min_uos": 4.5, "min_business_quality": 5.0},
                    "portfolio": {
                        "max_positions": 20, "sizing_method": "vol_parity",
                        "max_single_position": 0.08, "max_sector_exposure": 0.25,
                    },
                    "rebalance": {"frequency": "biweekly"},
                    "entry_rules": [
                        {"field": "case_score", "operator": "gte", "value": 60, "label": "CASE above 60"},
                    ],
                    "exit_rules": [
                        {"rule_type": "trailing_stop", "params": {"pct": 0.15}},
                        {"rule_type": "time_stop", "params": {"days": 120}},
                    ],
                    "regime_rules": [
                        {"regime": "bull", "action": "full_exposure"},
                        {"regime": "bear", "action": "reduce_50"},
                        {"regime": "high_vol", "action": "reduce_50", "sizing_override": 0.04},
                    ],
                    "metadata": {"category": "multi_factor", "horizon": "medium", "benchmark": "SPY",
                                 "tags": ["multi-factor", "diversified", "balanced"]},
                },
            },
        ]
