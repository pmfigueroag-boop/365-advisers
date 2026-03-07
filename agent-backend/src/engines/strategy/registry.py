"""
src/engines/strategy/registry.py
─────────────────────────────────────────────────────────────────────────────
StrategyRegistry — versioned strategy management with lineage tracking.

Builds on StrategyDefinition for strategy CRUD and adds:
  - Version history
  - Lineage tracking (parent strategies)
  - Strategy cloning
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.data.database import SessionLocal
from .definition import StrategyDefinition, StrategyConfig, StrategyCreate

logger = logging.getLogger("365advisers.strategy.registry")


class StrategyRegistry:
    """Extended registry with versioning and lineage."""

    def __init__(self):
        self._definition = StrategyDefinition()

    def create_strategy(self, name: str, description: str = "", config: dict | None = None) -> str:
        """Create a new strategy and return its ID."""
        cfg = StrategyConfig(**config) if config else StrategyConfig()
        payload = StrategyCreate(name=name, description=description, config=cfg)
        return self._definition.create(payload)

    def get_strategy(self, strategy_id: str) -> dict | None:
        """Get strategy summary."""
        summary = self._definition.get(strategy_id)
        return summary.model_dump() if summary else None

    def list_strategies(self, active_only: bool = True) -> list[dict]:
        """List all strategies."""
        summaries = self._definition.list_strategies(active_only)
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

    def get_predefined(self) -> list[dict]:
        """Return predefined strategy templates."""
        return [
            {
                "name": "Momentum Quality",
                "description": "Combines momentum signals with quality filters for trend-following with quality tilt",
                "config": {
                    "signal_filters": {
                        "required_categories": ["momentum", "quality"],
                        "min_signal_strength": 2.0,
                        "min_confidence": "medium",
                    },
                    "score_filters": {"min_uos": 5.0, "min_business_quality": 6.0, "min_case_score": 0},
                    "portfolio_rules": {
                        "max_positions": 15, "sizing_method": "vol_parity",
                        "rebalance_frequency": "weekly", "max_single_position": 0.08,
                        "max_sector_exposure": 0.25,
                    },
                },
            },
            {
                "name": "Value Contrarian",
                "description": "Deep value with mean reversion signals — patient, concentrated",
                "config": {
                    "signal_filters": {
                        "required_categories": ["value"],
                        "min_signal_strength": 1.0,
                        "min_confidence": "low",
                    },
                    "score_filters": {"min_uos": 4.0, "min_business_quality": 5.0, "min_case_score": 0},
                    "portfolio_rules": {
                        "max_positions": 10, "sizing_method": "equal",
                        "rebalance_frequency": "monthly", "max_single_position": 0.12,
                        "max_sector_exposure": 0.30,
                    },
                },
            },
            {
                "name": "Event Driven",
                "description": "Trades around filing events, institutional flow, and geopolitical events",
                "config": {
                    "signal_filters": {
                        "required_categories": ["event", "institutional"],
                        "min_signal_strength": 2.0,
                        "min_confidence": "medium",
                    },
                    "score_filters": {"min_uos": 3.0, "min_business_quality": 0.0, "min_case_score": 0},
                    "portfolio_rules": {
                        "max_positions": 20, "sizing_method": "equal",
                        "rebalance_frequency": "daily", "max_single_position": 0.06,
                        "max_sector_exposure": 0.20,
                    },
                },
            },
            {
                "name": "AI Infrastructure",
                "description": "Focused on AI/tech infrastructure with growth and technical momentum",
                "config": {
                    "signal_filters": {
                        "required_categories": ["growth", "momentum", "technical"],
                        "min_signal_strength": 2.0,
                        "min_confidence": "medium",
                    },
                    "score_filters": {"min_uos": 5.0, "min_business_quality": 7.0, "min_case_score": 0},
                    "portfolio_rules": {
                        "max_positions": 12, "sizing_method": "rank_weighted",
                        "rebalance_frequency": "monthly", "max_single_position": 0.10,
                        "max_sector_exposure": 0.40,
                    },
                },
            },
        ]
