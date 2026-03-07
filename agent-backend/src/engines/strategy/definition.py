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


class StrategyConfig(BaseModel):
    """Declarative strategy configuration."""
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
