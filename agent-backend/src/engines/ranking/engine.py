"""
src/engines/ranking/engine.py
──────────────────────────────────────────────────────────────────────────────
Global Opportunity Ranking Engine.

Aggregates Composite Alpha Score, Opportunity Score, and Signal Strength
into a Unified Opportunity Score (UOS) and produces ranked lists with
global, sector, and strategy views plus conviction-weighted allocations.

Pipeline:
  1. Normalise input scores to [0, 1]
  2. Compute UOS per asset
  3. Apply confidence adjustment
  4. Assign tier labels
  5. Sort globally
  6. Group by sector and strategy
  7. Compute suggested allocations for top N
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from src.engines.ranking.models import (
    OpportunityTier,
    RankedOpportunity,
    RankingConfig,
    RankingResult,
)

logger = logging.getLogger("365advisers.ranking.engine")


class RankingEngine:
    """
    Produces a unified ranking of all analysed assets.

    Usage
    -----
    engine = RankingEngine()
    result = engine.rank(ideas, case_scores, opp_scores)
    """

    def __init__(self, config: RankingConfig | None = None) -> None:
        self.config = config or RankingConfig()

    # ── Public API ────────────────────────────────────────────────────────

    def rank(
        self,
        ideas: list[dict],
        case_scores: dict[str, float] | None = None,
        opp_scores: dict[str, float] | None = None,
    ) -> RankingResult:
        """
        Compute the full ranking from input data.

        Parameters
        ----------
        ideas : list[dict]
            List of idea dicts with keys: ticker, name, sector, idea_type,
            signal_strength, confidence, signal_count, metadata, id.
        case_scores : dict | None
            {ticker: composite_alpha_score (0-100)}.
        opp_scores : dict | None
            {ticker: opportunity_score (0-10)}.

        Returns
        -------
        RankingResult
            Complete ranking with global, sector, strategy views.
        """
        case_scores = case_scores or {}
        opp_scores = opp_scores or {}
        cfg = self.config

        # Step 1-4: Build ranked opportunities
        ranked: list[RankedOpportunity] = []

        for idea in ideas:
            ticker = idea.get("ticker", "")
            case = case_scores.get(ticker, 0.0)
            opp = opp_scores.get(ticker, 5.0)
            strength = idea.get("signal_strength", 0.0)
            confidence = idea.get("confidence", "low")

            uos = self._compute_uos(case, opp, strength, confidence)
            tier = self._assign_tier(uos)

            ranked.append(RankedOpportunity(
                ticker=ticker,
                name=idea.get("name", ""),
                sector=idea.get("sector", "Unknown"),
                idea_type=idea.get("idea_type", ""),
                uos=round(uos, 1),
                tier=tier,
                case_score=round(case, 1),
                opportunity_score=round(opp, 2),
                signal_strength=round(strength, 3),
                confidence=confidence,
                signal_count=idea.get("signal_count", 0),
                idea_id=idea.get("id", ""),
                metadata=idea.get("metadata", {}),
            ))

        # Step 5: Sort globally by UOS descending
        ranked.sort(key=lambda r: r.uos, reverse=True)

        # Assign ranks
        for i, r in enumerate(ranked, start=1):
            r.rank = i

        # Step 6: Group by sector and strategy
        by_sector = self._group_by_sector(ranked)
        by_strategy = self._group_by_strategy(ranked)

        # Step 7: Compute allocations for top N
        top_n = ranked[:cfg.top_n]
        top_n = self._compute_allocations(top_n)

        logger.info(
            f"RANKING: {len(ranked)} assets ranked, "
            f"top UOS={ranked[0].uos if ranked else 0}"
        )

        return RankingResult(
            global_ranking=ranked,
            by_sector=by_sector,
            by_strategy=by_strategy,
            top_n=top_n,
            universe_size=len(ranked),
            config=cfg,
        )

    # ── UOS Formula ───────────────────────────────────────────────────────

    def _compute_uos(
        self,
        case_score: float,
        opp_score: float,
        signal_strength: float,
        confidence: str,
    ) -> float:
        """
        Unified Opportunity Score (UOS).

        UOS = (w₁ × CASE/100 + w₂ × Opp/10 + w₃ × Strength) × 100
              × Confidence_Multiplier
        """
        cfg = self.config

        # Normalise to [0, 1]
        case_norm = max(0.0, min(1.0, case_score / 100.0))
        opp_norm = max(0.0, min(1.0, opp_score / 10.0))
        str_norm = max(0.0, min(1.0, signal_strength))

        # Weighted sum
        raw = (
            cfg.w_case * case_norm
            + cfg.w_opp_score * opp_norm
            + cfg.w_signal_strength * str_norm
        )

        # Scale to 0-100
        uos = raw * 100.0

        # Confidence adjustment
        conf_mult = cfg.confidence_multipliers.get(confidence, 0.65)
        uos *= conf_mult

        return max(0.0, min(100.0, uos))

    # ── Tier Classification ───────────────────────────────────────────────

    @staticmethod
    def _assign_tier(uos: float) -> OpportunityTier:
        """Map UOS to a tier label."""
        if uos >= 80:
            return OpportunityTier.TOP_TIER
        elif uos >= 60:
            return OpportunityTier.STRONG
        elif uos >= 40:
            return OpportunityTier.MODERATE
        elif uos >= 20:
            return OpportunityTier.WEAK
        return OpportunityTier.AVOID

    # ── Allocation Model ──────────────────────────────────────────────────

    def _compute_allocations(
        self,
        top: list[RankedOpportunity],
    ) -> list[RankedOpportunity]:
        """
        Conviction-weighted allocation for top N assets.

        Raw_Alloc = UOS² / Σ UOS²
        Then constrained to [min_alloc, max_alloc].
        """
        cfg = self.config

        if not top:
            return top

        # Squared UOS for concentration
        uos_sq = [r.uos ** 2 for r in top]
        total_sq = sum(uos_sq) or 1.0

        # Raw allocation
        raw_allocs = [(sq / total_sq) * 100.0 for sq in uos_sq]

        # Apply constraints
        constrained = []
        for alloc in raw_allocs:
            clamped = max(cfg.min_alloc_pct, min(cfg.max_alloc_pct, alloc))
            constrained.append(clamped)

        # Normalise so allocations sum to 100%
        total_constrained = sum(constrained) or 1.0
        for i, r in enumerate(top):
            r.suggested_alloc_pct = round(
                (constrained[i] / total_constrained) * 100.0, 1
            )

        return top

    # ── Grouping ──────────────────────────────────────────────────────────

    @staticmethod
    def _group_by_sector(
        ranked: list[RankedOpportunity],
    ) -> dict[str, list[RankedOpportunity]]:
        """Group ranked assets by sector."""
        groups: dict[str, list[RankedOpportunity]] = defaultdict(list)
        for r in ranked:
            groups[r.sector or "Unknown"].append(r)
        return dict(groups)

    @staticmethod
    def _group_by_strategy(
        ranked: list[RankedOpportunity],
    ) -> dict[str, list[RankedOpportunity]]:
        """Group ranked assets by idea type (strategy)."""
        groups: dict[str, list[RankedOpportunity]] = defaultdict(list)
        for r in ranked:
            if r.idea_type:
                groups[r.idea_type].append(r)
        return dict(groups)
