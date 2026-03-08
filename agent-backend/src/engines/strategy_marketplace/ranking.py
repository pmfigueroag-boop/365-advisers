"""
src/engines/strategy_marketplace/ranking.py
─────────────────────────────────────────────────────────────────────────────
MarketplaceRanking — rank published strategies by multiple dimensions.

6 ranking categories:
  1. Top Performing (Sharpe + CAGR)
  2. Most Stable (stability score)
  3. Most Robust (quality score)
  4. Most Efficient (low turnover + cost)
  5. Most Validated (validation score)
  6. Rising Stars (recent improvement)
"""

from __future__ import annotations

import logging
from typing import Any

from .models import PublishedStrategy

logger = logging.getLogger("365advisers.strategy_marketplace.ranking")


class MarketplaceRanking:
    """Rank marketplace strategies across 6 dimensions."""

    @staticmethod
    def rank_all(listings: list[PublishedStrategy]) -> dict:
        """Generate all 6 rankings from the marketplace listings."""
        active = [l for l in listings if l.status.value != "delisted"]
        if not active:
            return {"rankings": {}, "total_strategies": 0}

        return {
            "total_strategies": len(active),
            "rankings": {
                "top_performing": MarketplaceRanking._rank_performance(active),
                "most_stable": MarketplaceRanking._rank_stability(active),
                "most_robust": MarketplaceRanking._rank_robustness(active),
                "most_efficient": MarketplaceRanking._rank_efficiency(active),
                "most_validated": MarketplaceRanking._rank_validated(active),
                "rising_stars": MarketplaceRanking._rank_rising(active),
            },
        }

    @staticmethod
    def get_leaderboard(listings: list[PublishedStrategy], category: str, top_n: int = 10) -> list[dict]:
        """Get a specific ranking leaderboard."""
        all_ranks = MarketplaceRanking.rank_all(listings)
        return all_ranks.get("rankings", {}).get(category, [])[:top_n]

    # ── Ranking Dimensions ────────────────────────────────────────────────

    @staticmethod
    def _rank_performance(listings: list[PublishedStrategy]) -> list[dict]:
        """Rank by risk-adjusted returns (Sharpe + CAGR)."""
        scored = []
        for l in listings:
            bs = l.backtest_summary
            sharpe = bs.get("sharpe_ratio", 0)
            cagr = bs.get("cagr", 0)
            composite = 0.6 * _normalize(sharpe, 0, 3) + 0.4 * _normalize(cagr, 0, 0.5)
            scored.append({
                "listing_id": l.listing_id,
                "name": l.name,
                "sharpe_ratio": sharpe,
                "cagr": cagr,
                "composite_score": round(composite * 100, 1),
            })
        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        for i, s in enumerate(scored):
            s["rank"] = i + 1
        return scored[:10]

    @staticmethod
    def _rank_stability(listings: list[PublishedStrategy]) -> list[dict]:
        """Rank by stability score."""
        scored = []
        for l in listings:
            score = l.trust_badges.get("stability_score", 0)
            scored.append({
                "listing_id": l.listing_id,
                "name": l.name,
                "stability_score": score,
            })
        scored.sort(key=lambda x: x["stability_score"], reverse=True)
        for i, s in enumerate(scored):
            s["rank"] = i + 1
        return scored[:10]

    @staticmethod
    def _rank_robustness(listings: list[PublishedStrategy]) -> list[dict]:
        """Rank by quality score (from StrategyScorecard)."""
        scored = []
        for l in listings:
            score = l.trust_badges.get("quality_score", 0)
            scored.append({
                "listing_id": l.listing_id,
                "name": l.name,
                "quality_score": score,
                "quality_grade": l.quality_grade,
            })
        scored.sort(key=lambda x: x["quality_score"], reverse=True)
        for i, s in enumerate(scored):
            s["rank"] = i + 1
        return scored[:10]

    @staticmethod
    def _rank_efficiency(listings: list[PublishedStrategy]) -> list[dict]:
        """Rank by cost efficiency (low turnover, low cost drag)."""
        scored = []
        for l in listings:
            bs = l.backtest_summary
            turnover = bs.get("turnover", 1.0)
            cost_drag = bs.get("cost_drag_bps", 50)
            # Lower is better — invert
            efficiency = 100 - (_normalize(turnover, 0, 5) * 50 + _normalize(cost_drag, 0, 200) * 50)
            scored.append({
                "listing_id": l.listing_id,
                "name": l.name,
                "turnover": turnover,
                "cost_drag_bps": cost_drag,
                "efficiency_score": round(max(efficiency, 0), 1),
            })
        scored.sort(key=lambda x: x["efficiency_score"], reverse=True)
        for i, s in enumerate(scored):
            s["rank"] = i + 1
        return scored[:10]

    @staticmethod
    def _rank_validated(listings: list[PublishedStrategy]) -> list[dict]:
        """Rank by validation depth."""
        scored = []
        for l in listings:
            val = l.trust_badges.get("validation_score", 0)
            repro = l.trust_badges.get("reproducibility_score", 0)
            depth = l.trust_badges.get("research_depth_score", 0)
            composite = 0.5 * val + 0.25 * repro + 0.25 * depth
            scored.append({
                "listing_id": l.listing_id,
                "name": l.name,
                "validation_score": val,
                "reproducibility_score": repro,
                "research_depth_score": depth,
                "composite_score": round(composite, 1),
            })
        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        for i, s in enumerate(scored):
            s["rank"] = i + 1
        return scored[:10]

    @staticmethod
    def _rank_rising(listings: list[PublishedStrategy]) -> list[dict]:
        """Rank by recent marketplace score (proxy for improvement)."""
        scored = []
        for l in listings:
            # Use marketplace_score as a proxy; in production would track history
            scored.append({
                "listing_id": l.listing_id,
                "name": l.name,
                "marketplace_score": l.marketplace_score,
                "download_count": l.download_count,
            })
        scored.sort(key=lambda x: x["marketplace_score"], reverse=True)
        for i, s in enumerate(scored):
            s["rank"] = i + 1
        return scored[:10]


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to [0, 1] range."""
    if max_val == min_val:
        return 0
    return max(0, min(1, (value - min_val) / (max_val - min_val)))
