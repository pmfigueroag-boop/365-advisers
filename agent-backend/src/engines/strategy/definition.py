"""
src/engines/strategy/definition.py
─────────────────────────────────────────────────────────────────────────────
StrategyDefinition — CRUD for named investment strategies.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.strategy.definition")


class EntryRule(BaseModel):
    """Declarative entry condition beyond signal filters."""
    field: str              # Field to evaluate: "case_score", "crowding", "uos"
    operator: str           # "gt", "lt", "gte", "lte", "eq", "in", "not_in"
    value: float | str | list = 0
    priority: int = 0       # Evaluation order (lower = first)
    label: str = ""         # Human-readable description


class ExitRule(BaseModel):
    """Declarative exit condition."""
    rule_type: str           # "trailing_stop", "time_stop", "signal_reversal", "target_reached"
    params: dict[str, Any] = Field(default_factory=dict)
    # Examples:
    #   trailing_stop: {"pct": 0.15}
    #   time_stop: {"days": 60}
    #   signal_reversal: {"signal_categories": ["momentum"]}
    #   target_reached: {"return_pct": 0.30}


class RegimeAction(BaseModel):
    """Action to take for a specific market regime."""
    regime: str              # "bull", "bear", "high_vol", "low_vol", "range"
    action: str              # "full_exposure", "reduce_50", "no_new_entries", "exit_all"
    sizing_override: float | None = None  # Override max_single_position


class UniverseConfig(BaseModel):
    """Asset universe definition."""
    source: str = "all"              # "all", "sp500", "nasdaq100", "custom"
    custom_tickers: list[str] = Field(default_factory=list)
    sector_filter: list[str] = Field(default_factory=list)
    min_market_cap: float | None = None
    min_adv: float | None = None     # Minimum average daily volume USD


class StrategyMetadata(BaseModel):
    """Descriptive metadata for strategy classification."""
    strategy_type: str = "systematic"    # systematic | discretionary | hybrid
    horizon: str = "medium"              # short | medium | long
    expected_turnover: str = "medium"    # low | medium | high
    tags: list[str] = Field(default_factory=list)


class StrategyConfig(BaseModel):
    """Declarative strategy configuration."""
    # ── Original fields (backward-compatible) ──
    signal_filters: dict[str, Any] = Field(default_factory=lambda: {
        "required_categories": [],
        "min_signal_strength": 0.0,
        "min_confidence": "low",
    })
    score_filters: dict[str, Any] = Field(default_factory=lambda: {
        "min_case_score": 0,
        "min_business_quality": 0.0,
        "min_uos": 0.0,
    })
    portfolio_rules: dict[str, Any] = Field(default_factory=lambda: {
        "max_positions": 20,
        "sizing_method": "vol_parity",
        "rebalance_frequency": "weekly",
        "max_single_position": 0.10,
        "max_sector_exposure": 0.25,
    })

    # ── Strategy Research Lab extensions ──
    entry_rules: list[EntryRule] = Field(default_factory=list)
    exit_rules: list[ExitRule] = Field(default_factory=list)
    regime_rules: list[RegimeAction] = Field(default_factory=list)
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    metadata: StrategyMetadata = Field(default_factory=StrategyMetadata)


class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    config: StrategyConfig = Field(default_factory=StrategyConfig)
    created_by: str = "manual"


class StrategySummary(BaseModel):
    strategy_id: str
    name: str
    description: str
    config: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class StrategyDefinition:
    """CRUD for named investment strategies."""

    def create(self, payload: StrategyCreate) -> str:
        from src.data.database import StrategyRecord

        strategy_id = uuid.uuid4().hex[:12]
        with SessionLocal() as db:
            record = StrategyRecord(
                strategy_id=strategy_id,
                name=payload.name,
                description=payload.description,
                config_json=payload.config.model_dump_json(),
                created_by=payload.created_by,
            )
            db.add(record)
            db.commit()

        logger.info("Strategy created: %s — %s", strategy_id, payload.name)
        return strategy_id

    def get(self, strategy_id: str) -> StrategySummary | None:
        from src.data.database import StrategyRecord

        with SessionLocal() as db:
            row = db.query(StrategyRecord).filter(
                StrategyRecord.strategy_id == strategy_id
            ).first()
            return self._to_summary(row) if row else None

    def list_strategies(self, active_only: bool = True) -> list[StrategySummary]:
        from src.data.database import StrategyRecord

        with SessionLocal() as db:
            q = db.query(StrategyRecord)
            if active_only:
                q = q.filter(StrategyRecord.is_active == True)
            rows = q.order_by(StrategyRecord.created_at.desc()).all()
            return [self._to_summary(r) for r in rows]

    def update(self, strategy_id: str, config: StrategyConfig) -> bool:
        from src.data.database import StrategyRecord

        with SessionLocal() as db:
            row = db.query(StrategyRecord).filter(
                StrategyRecord.strategy_id == strategy_id
            ).first()
            if not row:
                return False
            row.config_json = config.model_dump_json()
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
        return True

    def deactivate(self, strategy_id: str) -> bool:
        from src.data.database import StrategyRecord

        with SessionLocal() as db:
            row = db.query(StrategyRecord).filter(
                StrategyRecord.strategy_id == strategy_id
            ).first()
            if not row:
                return False
            row.is_active = False
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
        return True

    @staticmethod
    def _to_summary(row) -> StrategySummary:
        return StrategySummary(
            strategy_id=row.strategy_id,
            name=row.name,
            description=row.description or "",
            config=json.loads(row.config_json or "{}"),
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
