"""
src/engines/shadow/manager.py
─────────────────────────────────────────────────────────────────────────────
ShadowPortfolioManager — CRUD for shadow portfolios and positions.
Completely isolated from the real Portfolio Engine.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from src.data.database import SessionLocal

from .models import (
    ShadowPortfolioCreate,
    ShadowPortfolioSummary,
    ShadowPortfolioType,
    ShadowPositionSummary,
)

logger = logging.getLogger("365advisers.shadow.manager")


class ShadowPortfolioManager:
    """CRUD operations for shadow portfolios."""

    def create(self, payload: ShadowPortfolioCreate) -> str:
        """Create a new shadow portfolio.  Returns portfolio_id."""
        from src.data.database import ShadowPortfolioRecord

        portfolio_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc)

        with SessionLocal() as db:
            record = ShadowPortfolioRecord(
                portfolio_id=portfolio_id,
                name=payload.name,
                portfolio_type=payload.portfolio_type.value,
                strategy_id=payload.strategy_id,
                config_json=json.dumps(payload.config),
                inception_date=now,
                is_active=True,
            )
            db.add(record)
            db.commit()

        logger.info("Shadow portfolio created: %s [%s]", portfolio_id, payload.portfolio_type.value)
        return portfolio_id

    def get(self, portfolio_id: str) -> ShadowPortfolioSummary | None:
        from src.data.database import ShadowPortfolioRecord, ShadowPositionRecord, ShadowSnapshotRecord

        with SessionLocal() as db:
            row = (
                db.query(ShadowPortfolioRecord)
                .filter(ShadowPortfolioRecord.portfolio_id == portfolio_id)
                .first()
            )
            if not row:
                return None

            # Get active positions
            positions = (
                db.query(ShadowPositionRecord)
                .filter(
                    ShadowPositionRecord.portfolio_id == portfolio_id,
                    ShadowPositionRecord.exit_date.is_(None),
                )
                .all()
            )

            # Get latest snapshot for NAV
            latest_snap = (
                db.query(ShadowSnapshotRecord)
                .filter(ShadowSnapshotRecord.portfolio_id == portfolio_id)
                .order_by(ShadowSnapshotRecord.snapshot_date.desc())
                .first()
            )

            pos_summaries = [
                ShadowPositionSummary(
                    ticker=p.ticker,
                    weight=p.weight,
                    entry_price=p.entry_price,
                    entry_date=p.entry_date,
                    exit_date=p.exit_date,
                    sizing_method=p.sizing_method or "vol_parity",
                )
                for p in positions
            ]

            return ShadowPortfolioSummary(
                portfolio_id=row.portfolio_id,
                name=row.name,
                portfolio_type=ShadowPortfolioType(row.portfolio_type),
                strategy_id=row.strategy_id,
                inception_date=row.inception_date,
                is_active=row.is_active,
                current_nav=latest_snap.nav if latest_snap else 100.0,
                total_return_pct=(
                    latest_snap.cumulative_return if latest_snap else 0.0
                ),
                max_drawdown=latest_snap.drawdown if latest_snap else 0.0,
                positions_count=len(positions),
                positions=pos_summaries,
            )

    def list_portfolios(
        self,
        portfolio_type: ShadowPortfolioType | None = None,
        active_only: bool = True,
    ) -> list[ShadowPortfolioSummary]:
        from src.data.database import ShadowPortfolioRecord

        with SessionLocal() as db:
            q = db.query(ShadowPortfolioRecord)
            if portfolio_type:
                q = q.filter(ShadowPortfolioRecord.portfolio_type == portfolio_type.value)
            if active_only:
                q = q.filter(ShadowPortfolioRecord.is_active == True)

            rows = q.order_by(ShadowPortfolioRecord.inception_date.desc()).all()

        return [self.get(r.portfolio_id) for r in rows if r]

    def add_position(
        self,
        portfolio_id: str,
        ticker: str,
        weight: float,
        entry_price: float,
        sizing_method: str = "vol_parity",
    ) -> int:
        """Add a position to a shadow portfolio."""
        from src.data.database import ShadowPositionRecord

        with SessionLocal() as db:
            record = ShadowPositionRecord(
                portfolio_id=portfolio_id,
                ticker=ticker,
                weight=weight,
                entry_price=entry_price,
                entry_date=datetime.now(timezone.utc),
                sizing_method=sizing_method,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id

    def close_position(self, portfolio_id: str, ticker: str, exit_price: float) -> bool:
        """Close an active position."""
        from src.data.database import ShadowPositionRecord

        with SessionLocal() as db:
            pos = (
                db.query(ShadowPositionRecord)
                .filter(
                    ShadowPositionRecord.portfolio_id == portfolio_id,
                    ShadowPositionRecord.ticker == ticker,
                    ShadowPositionRecord.exit_date.is_(None),
                )
                .first()
            )
            if not pos:
                return False

            pos.exit_price = exit_price
            pos.exit_date = datetime.now(timezone.utc)
            db.commit()
            return True

    def deactivate(self, portfolio_id: str) -> bool:
        from src.data.database import ShadowPortfolioRecord

        with SessionLocal() as db:
            row = (
                db.query(ShadowPortfolioRecord)
                .filter(ShadowPortfolioRecord.portfolio_id == portfolio_id)
                .first()
            )
            if not row:
                return False
            row.is_active = False
            db.commit()
            return True
