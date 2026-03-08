"""
src/engines/strategy_marketplace/engine.py
─────────────────────────────────────────────────────────────────────────────
StrategyMarketplace — publish, discover, search, filter, and import
strategies within the marketplace.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .models import (
    ListingStatus,
    MarketplaceSearchParams,
    PublishedStrategy,
    RiskLevel,
)

logger = logging.getLogger("365advisers.strategy_marketplace.engine")

# ── In-memory store ──
_listings: dict[str, PublishedStrategy] = {}

# Lifecycle gate: only strategies at or above this state can be published
_PUBLISHABLE_STATES = {"backtested", "validated", "paper", "live"}


class StrategyMarketplace:
    """Publish, discover, search, and import strategies."""

    # ── Publication ───────────────────────────────────────────────────────

    @staticmethod
    def publish(
        strategy_id: str,
        name: str,
        author: str = "system",
        description: str = "",
        strategy_type: str = "",
        version: str = "1.0.0",
        signals_used: list[str] | None = None,
        signal_categories: list[str] | None = None,
        parameters: dict | None = None,
        backtest_summary: dict | None = None,
        tags: list[str] | None = None,
        regime_compatibility: list[str] | None = None,
        risk_level: str = "medium",
        lifecycle_state: str = "backtested",
    ) -> PublishedStrategy | dict:
        """Publish a strategy to the marketplace.

        Requires lifecycle_state ∈ {backtested, validated, paper, live}.
        """
        if lifecycle_state not in _PUBLISHABLE_STATES:
            return {
                "error": f"Strategy must be at least 'backtested' to publish. Current: {lifecycle_state}",
                "allowed_states": list(_PUBLISHABLE_STATES),
            }

        listing_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        listing = PublishedStrategy(
            listing_id=listing_id,
            strategy_id=strategy_id,
            name=name,
            author=author,
            description=description,
            strategy_type=strategy_type,
            version=version,
            signals_used=signals_used or [],
            signal_categories=signal_categories or [],
            parameters=parameters or {},
            backtest_summary=backtest_summary or {},
            tags=tags or [],
            regime_compatibility=regime_compatibility or [],
            risk_level=RiskLevel(risk_level),
            published_at=now,
            updated_at=now,
        )

        _listings[listing_id] = listing
        logger.info("Published strategy %s as listing %s", strategy_id, listing_id)
        return listing

    # ── Discovery ─────────────────────────────────────────────────────────

    @staticmethod
    def search(params: MarketplaceSearchParams | None = None) -> list[PublishedStrategy]:
        """Search and filter marketplace listings."""
        if params is None:
            params = MarketplaceSearchParams()

        results = []
        for listing in _listings.values():
            if listing.status == ListingStatus.DELISTED:
                continue

            # Text search
            if params.search:
                search_lower = params.search.lower()
                searchable = f"{listing.name} {listing.description} {listing.strategy_type}".lower()
                if search_lower not in searchable:
                    continue

            # Type filter
            if params.strategy_type and listing.strategy_type != params.strategy_type:
                continue

            # Risk level
            if params.risk_level and listing.risk_level.value != params.risk_level:
                continue

            # Quality score
            if params.min_quality_score is not None:
                qs = listing.trust_badges.get("quality_score", 0)
                if qs < params.min_quality_score:
                    continue

            # Sharpe
            if params.min_sharpe is not None:
                sharpe = listing.backtest_summary.get("sharpe_ratio", 0)
                if sharpe < params.min_sharpe:
                    continue

            # Max drawdown
            if params.max_drawdown is not None:
                dd = listing.backtest_summary.get("max_drawdown", 0)
                if dd < params.max_drawdown:  # dd is negative
                    continue

            # Regime
            if params.regime:
                if params.regime not in listing.regime_compatibility:
                    continue

            # Signals
            if params.signals:
                if not any(s in listing.signals_used for s in params.signals):
                    continue

            # Tags
            if params.tags:
                if not all(t in listing.tags for t in params.tags):
                    continue

            results.append(listing)

        # Sort
        sort_key = params.sort_by
        sort_map = {
            "marketplace_score": lambda l: l.marketplace_score,
            "sharpe": lambda l: l.backtest_summary.get("sharpe_ratio", 0),
            "cagr": lambda l: l.backtest_summary.get("cagr", 0),
            "downloads": lambda l: l.download_count,
            "published_at": lambda l: l.published_at or "",
            "stability": lambda l: l.trust_badges.get("stability_score", 0),
        }
        key_fn = sort_map.get(sort_key, sort_map["marketplace_score"])
        results.sort(key=key_fn, reverse=True)

        return results[:params.limit]

    @staticmethod
    def get(listing_id: str) -> PublishedStrategy | None:
        return _listings.get(listing_id)

    @staticmethod
    def get_by_strategy(strategy_id: str) -> PublishedStrategy | None:
        for listing in _listings.values():
            if listing.strategy_id == strategy_id:
                return listing
        return None

    # ── Import / Reuse ────────────────────────────────────────────────────

    @staticmethod
    def import_strategy(listing_id: str, new_name: str | None = None) -> dict:
        """Import a strategy from the marketplace. Returns clone info."""
        listing = _listings.get(listing_id)
        if not listing:
            return {"error": "Listing not found"}

        listing.download_count += 1

        return {
            "source_listing_id": listing_id,
            "source_strategy_id": listing.strategy_id,
            "source_name": listing.name,
            "cloned_name": new_name or f"{listing.name} (imported)",
            "config": listing.parameters,
            "signals_used": listing.signals_used,
            "download_count": listing.download_count,
        }

    # ── Management ────────────────────────────────────────────────────────

    @staticmethod
    def delist(listing_id: str) -> bool:
        if listing_id in _listings:
            _listings[listing_id].status = ListingStatus.DELISTED
            return True
        return False

    @staticmethod
    def feature(listing_id: str) -> bool:
        if listing_id in _listings:
            _listings[listing_id].status = ListingStatus.FEATURED
            return True
        return False

    @staticmethod
    def update_badges(listing_id: str, badges: dict[str, float]) -> bool:
        """Update trust badges and recompute marketplace score."""
        listing = _listings.get(listing_id)
        if not listing:
            return False

        listing.trust_badges.update(badges)
        listing.marketplace_score = _compute_marketplace_score(listing.trust_badges)
        listing.quality_grade = _classify_grade(listing.trust_badges.get("quality_score", 0))
        listing.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    @staticmethod
    def clear():
        _listings.clear()


def _compute_marketplace_score(badges: dict[str, float]) -> float:
    """Compute composite marketplace score from trust badges."""
    weights = {
        "quality_score": 0.30,
        "validation_score": 0.20,
        "stability_score": 0.20,
        "reproducibility_score": 0.15,
        "research_depth_score": 0.15,
    }
    score = sum(badges.get(k, 0) * w for k, w in weights.items())
    return round(score, 2)


def _classify_grade(quality_score: float) -> str:
    if quality_score >= 90:
        return "A+"
    elif quality_score >= 80:
        return "A"
    elif quality_score >= 70:
        return "B+"
    elif quality_score >= 60:
        return "B"
    elif quality_score >= 50:
        return "C+"
    else:
        return "C"
