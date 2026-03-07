"""
src/engines/signal_discovery/generator.py
──────────────────────────────────────────────────────────────────────────────
Feature combination generator.

Produces candidate signal definitions from:
  - Single threshold signals (feature > median)
  - Ratio signals (feature_A / feature_B)
  - Interaction signals (feature_A AND feature_B)
  - Z-score signals (zscore(feature) > k)
"""

from __future__ import annotations

import hashlib
import logging
from itertools import combinations

from src.engines.signal_discovery.models import (
    CandidateSignal,
    CandidateType,
    DiscoveryConfig,
)

logger = logging.getLogger("365advisers.signal_discovery.generator")


# Known feature paths by category
FUNDAMENTAL_FEATURES = [
    "fundamental.pe_ratio", "fundamental.pb_ratio", "fundamental.fcf_yield",
    "fundamental.dividend_yield", "fundamental.roe", "fundamental.debt_equity",
    "fundamental.revenue_growth", "fundamental.earnings_growth",
    "fundamental.current_ratio", "fundamental.gross_margin",
]

TECHNICAL_FEATURES = [
    "technical.rsi_14", "technical.macd_histogram", "technical.bb_position",
    "technical.adx", "technical.atr_pct", "technical.volume_ratio",
    "technical.price_vs_sma50", "technical.price_vs_sma200",
]

FLOW_FEATURES = [
    "flow.institutional_change", "flow.short_interest_ratio",
    "flow.insider_buying",
]


class FeatureGenerator:
    """
    Generates candidate signal definitions from feature combinations.
    """

    def __init__(self, config: DiscoveryConfig | None = None) -> None:
        self.config = config or DiscoveryConfig()

    def generate(
        self,
        features: list[str] | None = None,
        include_ratios: bool = True,
        include_interactions: bool = True,
        include_zscores: bool = True,
    ) -> list[CandidateSignal]:
        """
        Generate candidate signals from feature list.

        Parameters
        ----------
        features : list[str] | None
            Feature paths. If None, uses built-in feature lists.
        include_ratios, include_interactions, include_zscores : bool
            Toggle candidate types.

        Returns
        -------
        list[CandidateSignal]
        """
        feats = features or (FUNDAMENTAL_FEATURES + TECHNICAL_FEATURES + FLOW_FEATURES)
        candidates: list[CandidateSignal] = []

        # 1. Single threshold signals
        for feat in feats:
            cid = self._make_id(f"single_{feat}_above")
            candidates.append(CandidateSignal(
                candidate_id=cid,
                name=f"{feat.split('.')[-1]}_high",
                feature_formula=feat,
                candidate_type=CandidateType.SINGLE.value,
                direction="above",
                threshold=0.0,  # will be set to median during evaluation
                category=feat.split(".")[0],
            ))

            cid = self._make_id(f"single_{feat}_below")
            candidates.append(CandidateSignal(
                candidate_id=cid,
                name=f"{feat.split('.')[-1]}_low",
                feature_formula=feat,
                candidate_type=CandidateType.SINGLE.value,
                direction="below",
                threshold=0.0,
                category=feat.split(".")[0],
            ))

        # 2. Ratio signals (same category)
        if include_ratios:
            by_cat: dict[str, list[str]] = {}
            for f in feats:
                cat = f.split(".")[0]
                by_cat.setdefault(cat, []).append(f)

            for cat, cat_feats in by_cat.items():
                for a, b in combinations(cat_feats, 2):
                    cid = self._make_id(f"ratio_{a}_{b}")
                    candidates.append(CandidateSignal(
                        candidate_id=cid,
                        name=f"{a.split('.')[-1]}/{b.split('.')[-1]}",
                        feature_formula=f"{a} / {b}",
                        candidate_type=CandidateType.RATIO.value,
                        direction="above",
                        threshold=1.0,
                        category=cat,
                    ))

        # 3. Interaction signals (cross-category)
        if include_interactions:
            categories = list(set(f.split(".")[0] for f in feats))
            for i, cat_a in enumerate(categories):
                for cat_b in categories[i + 1:]:
                    feats_a = [f for f in feats if f.startswith(cat_a)]
                    feats_b = [f for f in feats if f.startswith(cat_b)]
                    for fa in feats_a[:3]:  # limit cross-category combos
                        for fb in feats_b[:3]:
                            cid = self._make_id(f"interact_{fa}_{fb}")
                            candidates.append(CandidateSignal(
                                candidate_id=cid,
                                name=f"{fa.split('.')[-1]}_AND_{fb.split('.')[-1]}",
                                feature_formula=f"{fa} AND {fb}",
                                candidate_type=CandidateType.INTERACTION.value,
                                direction="above",
                                threshold=0.0,
                                category="multi",
                            ))

        # 4. Z-score signals
        if include_zscores:
            for feat in feats:
                cid = self._make_id(f"zscore_{feat}")
                candidates.append(CandidateSignal(
                    candidate_id=cid,
                    name=f"zscore_{feat.split('.')[-1]}",
                    feature_formula=f"zscore({feat})",
                    candidate_type=CandidateType.ZSCORE.value,
                    direction="above",
                    threshold=1.5,
                    category=feat.split(".")[0],
                ))

        # Limit
        if len(candidates) > self.config.max_candidates:
            candidates = candidates[: self.config.max_candidates]

        logger.info("DISCOVERY-GEN: Generated %d candidates", len(candidates))
        return candidates

    @staticmethod
    def _make_id(seed: str) -> str:
        """Deterministic short ID from seed."""
        return hashlib.md5(seed.encode()).hexdigest()[:12]
