"""
src/engines/oms/position_sync.py
──────────────────────────────────────────────────────────────────────────────
Position reconciliation — compare local vs broker positions.
"""
from __future__ import annotations
import logging
from pydantic import BaseModel, Field
from src.engines.oms.models import PortfolioPosition

logger = logging.getLogger("365advisers.oms.position_sync")


class PositionMismatch(BaseModel):
    ticker: str
    local_qty: float = 0.0
    broker_qty: float = 0.0
    qty_diff: float = 0.0
    local_value: float = 0.0
    broker_value: float = 0.0
    value_diff: float = 0.0
    mismatch_type: str = ""  # "missing_local" | "missing_broker" | "quantity" | "price"


class SyncReport(BaseModel):
    total_local: int = 0
    total_broker: int = 0
    matched: int = 0
    mismatches: list[PositionMismatch] = Field(default_factory=list)
    is_synced: bool = True


class PositionSyncEngine:
    """Compare local positions against broker and produce sync report."""

    @classmethod
    def reconcile(
        cls,
        local_positions: list[PortfolioPosition],
        broker_positions: list[PortfolioPosition],
        tolerance_qty: float = 0.01,
        tolerance_pct: float = 0.02,
    ) -> SyncReport:
        local_map = {p.ticker: p for p in local_positions}
        broker_map = {p.ticker: p for p in broker_positions}
        all_tickers = set(local_map.keys()) | set(broker_map.keys())

        mismatches = []
        matched = 0

        for ticker in sorted(all_tickers):
            lp = local_map.get(ticker)
            bp = broker_map.get(ticker)

            if lp and not bp:
                mismatches.append(PositionMismatch(
                    ticker=ticker, local_qty=lp.quantity, broker_qty=0,
                    qty_diff=lp.quantity, local_value=lp.market_value,
                    mismatch_type="missing_broker",
                ))
            elif bp and not lp:
                mismatches.append(PositionMismatch(
                    ticker=ticker, broker_qty=bp.quantity, local_qty=0,
                    qty_diff=-bp.quantity, broker_value=bp.market_value,
                    mismatch_type="missing_local",
                ))
            elif lp and bp:
                qty_diff = abs(lp.quantity - bp.quantity)
                val_diff = abs(lp.market_value - bp.market_value)
                val_pct = val_diff / max(bp.market_value, 1)

                if qty_diff > tolerance_qty:
                    mismatches.append(PositionMismatch(
                        ticker=ticker, local_qty=lp.quantity, broker_qty=bp.quantity,
                        qty_diff=round(lp.quantity - bp.quantity, 4),
                        local_value=lp.market_value, broker_value=bp.market_value,
                        value_diff=round(val_diff, 2),
                        mismatch_type="quantity",
                    ))
                elif val_pct > tolerance_pct:
                    mismatches.append(PositionMismatch(
                        ticker=ticker, local_qty=lp.quantity, broker_qty=bp.quantity,
                        local_value=lp.market_value, broker_value=bp.market_value,
                        value_diff=round(val_diff, 2),
                        mismatch_type="price",
                    ))
                else:
                    matched += 1

        return SyncReport(
            total_local=len(local_positions),
            total_broker=len(broker_positions),
            matched=matched,
            mismatches=mismatches,
            is_synced=len(mismatches) == 0,
        )
