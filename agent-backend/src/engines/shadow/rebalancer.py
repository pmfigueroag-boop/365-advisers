"""
src/engines/shadow/rebalancer.py
─────────────────────────────────────────────────────────────────────────────
ShadowRebalancer — Applies rebalancing logic to shadow portfolios based
on the latest idea universe and ranking data.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.shadow.rebalancer")


class ShadowRebalancer:
    """Rebalances shadow portfolios based on the latest ideas and rankings."""

    def rebalance_research_portfolio(
        self,
        portfolio_id: str,
        current_prices: dict[str, float],
        max_positions: int = 20,
    ) -> dict:
        """Rebalance the research portfolio using top-ranked IGE ideas.

        Returns a summary of changes made.
        """
        from src.data.database import (
            IdeaRecord,
            ShadowPortfolioRecord,
            ShadowPositionRecord,
            ShadowSnapshotRecord,
        )

        changes = {"added": [], "removed": [], "reweighted": []}

        with SessionLocal() as db:
            portfolio = (
                db.query(ShadowPortfolioRecord)
                .filter(ShadowPortfolioRecord.portfolio_id == portfolio_id)
                .first()
            )
            if not portfolio or not portfolio.is_active:
                return {"error": "Portfolio not found or inactive"}

            config = json.loads(portfolio.config_json or "{}")

            # Get current active ideas, sorted by priority
            ideas = (
                db.query(IdeaRecord)
                .filter(IdeaRecord.status == "active")
                .order_by(IdeaRecord.priority.desc())
                .limit(max_positions)
                .all()
            )

            target_tickers = {idea.ticker for idea in ideas}

            # Get current positions
            current_positions = (
                db.query(ShadowPositionRecord)
                .filter(
                    ShadowPositionRecord.portfolio_id == portfolio_id,
                    ShadowPositionRecord.exit_date.is_(None),
                )
                .all()
            )
            current_tickers = {p.ticker for p in current_positions}

            # Close positions not in target
            for pos in current_positions:
                if pos.ticker not in target_tickers:
                    price = current_prices.get(pos.ticker, pos.entry_price)
                    pos.exit_price = price
                    pos.exit_date = datetime.now(timezone.utc)
                    changes["removed"].append(pos.ticker)

            # Open new positions
            n_target = len(target_tickers)
            equal_weight = 1.0 / max(n_target, 1)

            for idea in ideas:
                if idea.ticker not in current_tickers:
                    price = current_prices.get(idea.ticker)
                    if price is None:
                        continue
                    new_pos = ShadowPositionRecord(
                        portfolio_id=portfolio_id,
                        ticker=idea.ticker,
                        weight=equal_weight,
                        entry_price=price,
                        entry_date=datetime.now(timezone.utc),
                        sizing_method=config.get("sizing_method", "equal_weight"),
                    )
                    db.add(new_pos)
                    changes["added"].append(idea.ticker)

            # Take a snapshot
            latest_snap = (
                db.query(ShadowSnapshotRecord)
                .filter(ShadowSnapshotRecord.portfolio_id == portfolio_id)
                .order_by(ShadowSnapshotRecord.snapshot_date.desc())
                .first()
            )
            prev_nav = latest_snap.nav if latest_snap else 100.0

            # Calculate new NAV based on position returns
            total_return = 0.0
            active_count = 0
            for pos in current_positions:
                if pos.exit_date is None and pos.ticker in target_tickers:
                    price = current_prices.get(pos.ticker, pos.entry_price)
                    ret = (price - pos.entry_price) / pos.entry_price if pos.entry_price else 0.0
                    total_return += ret * pos.weight
                    active_count += 1

            daily_return = total_return
            new_nav = prev_nav * (1 + daily_return)
            cumulative = (new_nav - 100.0) / 100.0
            drawdown = min(0.0, cumulative)  # Simplified

            snapshot = ShadowSnapshotRecord(
                portfolio_id=portfolio_id,
                snapshot_date=datetime.now(timezone.utc),
                nav=round(new_nav, 4),
                daily_return=round(daily_return, 6),
                cumulative_return=round(cumulative, 6),
                drawdown=round(drawdown, 6),
                positions_count=active_count + len(changes["added"]),
            )
            db.add(snapshot)
            db.commit()

        logger.info(
            "Rebalanced %s: +%d -%d positions, NAV=%.2f",
            portfolio_id,
            len(changes["added"]),
            len(changes["removed"]),
            new_nav,
        )
        return changes

    def rebalance_benchmark(
        self,
        portfolio_id: str,
        benchmark_price: float,
    ) -> dict:
        """Update the benchmark portfolio (simple buy-and-hold tracking)."""
        from src.data.database import ShadowSnapshotRecord, ShadowPortfolioRecord

        with SessionLocal() as db:
            portfolio = (
                db.query(ShadowPortfolioRecord)
                .filter(ShadowPortfolioRecord.portfolio_id == portfolio_id)
                .first()
            )
            if not portfolio:
                return {"error": "Portfolio not found"}

            config = json.loads(portfolio.config_json or "{}")
            initial_price = config.get("benchmark_entry_price", benchmark_price)

            # If first snapshot, store the entry price
            if "benchmark_entry_price" not in config:
                config["benchmark_entry_price"] = benchmark_price
                portfolio.config_json = json.dumps(config)

            nav = 100.0 * (benchmark_price / initial_price)
            cumulative = (nav - 100.0) / 100.0

            latest = (
                db.query(ShadowSnapshotRecord)
                .filter(ShadowSnapshotRecord.portfolio_id == portfolio_id)
                .order_by(ShadowSnapshotRecord.snapshot_date.desc())
                .first()
            )
            prev_nav = latest.nav if latest else 100.0
            daily_return = (nav - prev_nav) / prev_nav if prev_nav > 0 else 0.0

            snap = ShadowSnapshotRecord(
                portfolio_id=portfolio_id,
                snapshot_date=datetime.now(timezone.utc),
                nav=round(nav, 4),
                daily_return=round(daily_return, 6),
                cumulative_return=round(cumulative, 6),
                drawdown=round(min(0.0, cumulative), 6),
                positions_count=1,
            )
            db.add(snap)
            db.commit()

        return {"nav": round(nav, 4), "cumulative_return": round(cumulative, 6)}
