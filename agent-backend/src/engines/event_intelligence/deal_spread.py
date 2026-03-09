"""
src/engines/event_intelligence/deal_spread.py
──────────────────────────────────────────────────────────────────────────────
M&A Deal-Spread Tracker.

Tracks announced M&A deals, computes the deal spread (difference
between offer price and current market price), and calculates
annualized returns for merger-arbitrage analysis.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.engines.event_intelligence.models import (
    DealSpread,
    DealStatus,
)

logger = logging.getLogger("365advisers.event_intelligence.deal_spread")


class DealTracker:
    """
    In-memory M&A deal tracker.

    Tracks active deals and computes:
        - Raw spread: (deal_price - current_price) / current_price
        - Annualized spread: raw spread scaled to annual return
    """

    def __init__(self) -> None:
        self._deals: dict[str, DealSpread] = {}  # keyed by deal_id

    # ── CRUD ─────────────────────────────────────────────────────────────

    def add_deal(
        self,
        acquirer: str,
        target: str,
        deal_price: float,
        current_price: float,
        announced_date: datetime | None = None,
        expected_close_date: datetime | None = None,
        deal_type: str = "cash",
        risk_factors: list[str] | None = None,
    ) -> DealSpread:
        """Register a new M&A deal."""
        deal_id = uuid4().hex[:10]
        ann_date = announced_date or datetime.now(timezone.utc)
        close_date = expected_close_date or (ann_date + timedelta(days=180))

        spread_pct = self._compute_spread(deal_price, current_price)
        ann_spread = self._annualize_spread(spread_pct, ann_date, close_date)

        deal = DealSpread(
            deal_id=deal_id,
            acquirer=acquirer,
            target=target,
            announced_date=ann_date,
            expected_close_date=close_date,
            deal_price=deal_price,
            current_price=current_price,
            spread_pct=round(spread_pct, 4),
            annualized_spread_pct=round(ann_spread, 4),
            deal_status=DealStatus.ANNOUNCED,
            deal_type=deal_type,
            risk_factors=risk_factors or [],
        )
        self._deals[deal_id] = deal
        logger.info("Deal registered: %s acquiring %s at $%.2f (spread: %.2f%%)",
                     acquirer, target, deal_price, spread_pct * 100)
        return deal

    def update_price(self, deal_id: str, current_price: float) -> DealSpread | None:
        """Update current price and recalculate spreads."""
        deal = self._deals.get(deal_id)
        if not deal:
            return None

        deal.current_price = current_price
        deal.spread_pct = round(self._compute_spread(deal.deal_price, current_price), 4)
        if deal.expected_close_date:
            deal.annualized_spread_pct = round(
                self._annualize_spread(
                    deal.spread_pct,
                    datetime.now(timezone.utc),
                    deal.expected_close_date,
                ), 4
            )
        return deal

    def update_status(self, deal_id: str, status: DealStatus) -> bool:
        """Update the deal status."""
        deal = self._deals.get(deal_id)
        if not deal:
            return False
        deal.deal_status = status
        return True

    def get_deal(self, deal_id: str) -> DealSpread | None:
        """Get a specific deal."""
        return self._deals.get(deal_id)

    def get_active_deals(self) -> list[DealSpread]:
        """Get all active (non-closed, non-terminated) deals."""
        active_statuses = {
            DealStatus.ANNOUNCED,
            DealStatus.REGULATORY_REVIEW,
            DealStatus.SHAREHOLDER_VOTE,
            DealStatus.APPROVED,
        }
        return [
            d for d in self._deals.values()
            if d.deal_status in active_statuses
        ]

    def get_deals_for_target(self, target_ticker: str) -> list[DealSpread]:
        """Get all deals for a specific target ticker."""
        return [d for d in self._deals.values() if d.target == target_ticker]

    @property
    def total_deals(self) -> int:
        return len(self._deals)

    # ── Calculations ─────────────────────────────────────────────────────

    @staticmethod
    def _compute_spread(deal_price: float, current_price: float) -> float:
        """Compute raw deal spread as a decimal."""
        if current_price <= 0:
            return 0.0
        return (deal_price - current_price) / current_price

    @staticmethod
    def _annualize_spread(
        spread: float,
        from_date: datetime,
        close_date: datetime,
    ) -> float:
        """Annualize the spread based on days to expected close."""
        from_utc = from_date.replace(tzinfo=timezone.utc) if from_date.tzinfo is None else from_date
        close_utc = close_date.replace(tzinfo=timezone.utc) if close_date.tzinfo is None else close_date
        days_to_close = max((close_utc - from_utc).days, 1)
        return spread * (365.0 / days_to_close)
