"""
src/engines/liquidity/estimator.py
─────────────────────────────────────────────────────────────────────────────
LiquidityEstimator — Estimates per-ticker liquidity profile including
ADV, bid-ask spread, market cap, and liquidity tier classification.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.liquidity.estimator")


class LiquidityEstimator:
    """Estimates and persists per-ticker liquidity profiles."""

    # Tier thresholds (ADV in shares)
    TIER_THRESHOLDS = {
        "high": 5_000_000,
        "medium": 1_000_000,
        "low": 200_000,
        # Below low → illiquid
    }

    def estimate(self, ticker: str, market_data: dict[str, Any]) -> dict:
        """Estimate liquidity profile from market data.

        Args:
            ticker: Stock ticker.
            market_data: Dict containing:
                - avg_volume_20d: 20-day average daily volume
                - avg_price: Average price over period
                - market_cap: Market capitalization
                - bid_ask_spread: Average bid-ask spread in $

        Returns:
            Liquidity profile dict.
        """
        adv = market_data.get("avg_volume_20d", 0)
        avg_price = market_data.get("avg_price", 1.0)
        market_cap = market_data.get("market_cap", 0)
        spread = market_data.get("bid_ask_spread", 0.01)

        # Spread in basis points
        spread_bps = (spread / avg_price * 10000) if avg_price > 0 else 0.0

        # Liquidity tier classification
        tier = "illiquid"
        for tier_name, threshold in sorted(
            self.TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True
        ):
            if adv >= threshold:
                tier = tier_name
                break

        # Market impact for 1% participation rate
        # Simplified Almgren-Chriss: impact ≈ k × √(participation)
        participation_1pct = 0.01
        k_factor = 0.1 if tier == "high" else 0.2 if tier == "medium" else 0.5
        impact_1pct = k_factor * (participation_1pct ** 0.5) * 10000  # bps

        # Capacity estimate: max AUM = ADV × avg_price × target_part × holding_period
        target_participation = 0.05
        holding_period = 20  # days
        capacity_usd = adv * avg_price * target_participation * holding_period

        profile = {
            "ticker": ticker,
            "avg_daily_volume_20d": adv,
            "avg_spread_bps": round(spread_bps, 2),
            "market_cap": market_cap,
            "estimated_impact_1pct": round(impact_1pct, 2),
            "estimated_capacity_usd": round(capacity_usd, 2),
            "liquidity_tier": tier,
        }

        # Persist to DB
        self._save_profile(profile)

        logger.info("Liquidity profile: %s — tier=%s, capacity=$%.0f", ticker, tier, capacity_usd)
        return profile

    def get_profile(self, ticker: str) -> dict | None:
        from src.data.database import LiquidityProfileRecord

        with SessionLocal() as db:
            row = (
                db.query(LiquidityProfileRecord)
                .filter(LiquidityProfileRecord.ticker == ticker)
                .order_by(LiquidityProfileRecord.updated_at.desc())
                .first()
            )
            if not row:
                return None
            return {
                "ticker": row.ticker,
                "avg_daily_volume_20d": row.avg_daily_volume_20d,
                "avg_spread_bps": row.avg_spread_bps,
                "market_cap": row.market_cap,
                "estimated_impact_1pct": row.estimated_impact_1pct,
                "estimated_capacity_usd": row.estimated_capacity_usd,
                "liquidity_tier": row.liquidity_tier,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }

    def get_all_profiles(self) -> list[dict]:
        from src.data.database import LiquidityProfileRecord

        with SessionLocal() as db:
            rows = db.query(LiquidityProfileRecord).order_by(
                LiquidityProfileRecord.ticker
            ).all()
            return [
                {
                    "ticker": r.ticker,
                    "liquidity_tier": r.liquidity_tier,
                    "estimated_capacity_usd": r.estimated_capacity_usd,
                    "avg_spread_bps": r.avg_spread_bps,
                }
                for r in rows
            ]

    def _save_profile(self, profile: dict) -> None:
        from src.data.database import LiquidityProfileRecord

        with SessionLocal() as db:
            # Upsert: find existing or create new
            existing = (
                db.query(LiquidityProfileRecord)
                .filter(LiquidityProfileRecord.ticker == profile["ticker"])
                .first()
            )
            if existing:
                existing.avg_daily_volume_20d = profile["avg_daily_volume_20d"]
                existing.avg_spread_bps = profile["avg_spread_bps"]
                existing.market_cap = profile["market_cap"]
                existing.estimated_impact_1pct = profile["estimated_impact_1pct"]
                existing.estimated_capacity_usd = profile["estimated_capacity_usd"]
                existing.liquidity_tier = profile["liquidity_tier"]
                existing.updated_at = datetime.now(timezone.utc)
            else:
                db.add(LiquidityProfileRecord(
                    ticker=profile["ticker"],
                    avg_daily_volume_20d=profile["avg_daily_volume_20d"],
                    avg_spread_bps=profile["avg_spread_bps"],
                    market_cap=profile["market_cap"],
                    estimated_impact_1pct=profile["estimated_impact_1pct"],
                    estimated_capacity_usd=profile["estimated_capacity_usd"],
                    liquidity_tier=profile["liquidity_tier"],
                ))
            db.commit()
