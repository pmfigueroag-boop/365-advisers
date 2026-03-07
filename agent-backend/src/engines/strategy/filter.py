"""
src/engines/strategy/filter.py
─────────────────────────────────────────────────────────────────────────────
StrategyFilter — Applies strategy criteria to ranked opportunities.
Runs as a post-filter on Global Ranking Engine output.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("365advisers.strategy.filter")


class StrategyFilter:
    """Filters ranked opportunities based on strategy criteria."""

    def apply(
        self,
        opportunities: list[dict[str, Any]],
        strategy_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Apply strategy filters to a list of ranked opportunities.

        Each opportunity dict should contain at least:
          - ticker, case_score, business_quality, uos
          - signal_categories (list of active signal category strings)
          - signal_strength, confidence

        Returns filtered list matching all strategy criteria.
        """
        sig_filters = strategy_config.get("signal_filters", {})
        score_filters = strategy_config.get("score_filters", {})

        required_cats = set(sig_filters.get("required_categories", []))
        min_strength = sig_filters.get("min_signal_strength", 0.0)
        min_confidence = sig_filters.get("min_confidence", "low")

        min_case = score_filters.get("min_case_score", 0)
        min_bq = score_filters.get("min_business_quality", 0.0)
        min_uos = score_filters.get("min_uos", 0.0)

        confidence_order = {"high": 3, "medium": 2, "low": 1}
        min_conf_level = confidence_order.get(min_confidence, 0)

        result = []
        for opp in opportunities:
            # Signal category filter
            if required_cats:
                active_cats = set(opp.get("signal_categories", []))
                if not required_cats.issubset(active_cats):
                    continue

            # Signal strength filter
            if opp.get("signal_strength", 0) < min_strength:
                continue

            # Confidence filter
            opp_conf = confidence_order.get(opp.get("confidence", "low"), 0)
            if opp_conf < min_conf_level:
                continue

            # Score filters
            if opp.get("case_score", 0) < min_case:
                continue
            if opp.get("business_quality", 0) < min_bq:
                continue
            if opp.get("uos", 0) < min_uos:
                continue

            result.append(opp)

        # Apply max_positions from portfolio rules
        portfolio_rules = strategy_config.get("portfolio_rules", {})
        max_positions = portfolio_rules.get("max_positions", 20)
        result = result[:max_positions]

        logger.info(
            "Strategy filter applied: %d → %d opportunities",
            len(opportunities),
            len(result),
        )
        return result
