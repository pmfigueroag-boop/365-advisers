"""
src/engines/composite_alpha/engine.py
──────────────────────────────────────────────────────────────────────────────
Composite Alpha Score Engine — orchestrates a 5-stage pipeline that
transforms a SignalProfile (from the Alpha Signals Library) into a
normalised, weighted CompositeAlphaResult (0–100 scale).

Pipeline:
  1. Normalizer      — raw signal values → 0–100 per signal
  2. CategoryAggregator — per-signal scores → category subscores
  3. ConflictResolver — detect and penalise contradictory signals
  4. WeightedScorer   — apply category weights → final 0–100 score
  5. Classifier       — map score → SignalEnvironment label
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    EvaluatedSignal,
    SignalCategory,
    SignalDirection,
    SignalProfile,
    SignalStrength,
)
from src.engines.alpha_signals.registry import registry
from src.engines.composite_alpha.models import (
    CASEWeightConfig,
    CategorySubscore,
    CompositeAlphaResult,
    SignalEnvironment,
)
from src.engines.alpha_decay.models import DecayAdjustedProfile, FreshnessLevel

logger = logging.getLogger("365advisers.composite_alpha.engine")


# ── Strength numeric map (reuse same mapping as evaluator) ────────────────────

_STRENGTH_NUMERIC = {
    SignalStrength.STRONG: 1.0,
    SignalStrength.MODERATE: 0.6,
    SignalStrength.WEAK: 0.3,
}

# ── Cross-category conflict pairs ────────────────────────────────────────────

_CROSS_CATEGORY_CONFLICTS = [
    # (category_a, category_b, description)
    ("momentum", "volatility", "Momentum vs Volatility: trend may be unsustainable"),
    ("value", "quality", "Value vs Quality: potential value trap"),
    ("growth", "macro", "Growth vs Macro: headwind environment"),
]

# ── Convergence bonus thresholds ─────────────────────────────────────────────

_CONVERGENCE_BONUS_5 = 3.0   # +3 when >= 5 active categories
_CONVERGENCE_BONUS_7 = 5.0   # +5 when >= 7 active categories


class CompositeAlphaEngine:
    """
    Stateless engine that produces a CompositeAlphaResult from a SignalProfile.

    Usage::

        engine = CompositeAlphaEngine()
        result = engine.compute(signal_profile)

        # With custom weights:
        result = engine.compute(signal_profile, weights=CASEWeightConfig(value=0.30, ...))
    """

    def compute(
        self,
        profile: SignalProfile,
        weights: CASEWeightConfig | None = None,
        decay_engine: "DecayEngine | None" = None,
    ) -> CompositeAlphaResult:
        """
        Run the full pipeline (6 stages when decay is active).

        Parameters
        ----------
        profile : SignalProfile
            Evaluated signal profile from the Alpha Signals Evaluator.
        weights : CASEWeightConfig | None
            Optional custom weight profile.  Uses defaults if not provided.
        decay_engine : DecayEngine | None
            Optional decay engine.  When provided, Stage 0 applies temporal
            decay before normalization.

        Returns
        -------
        CompositeAlphaResult
            Complete composite score with subscores, environment, and
            freshness metadata.
        """
        if weights is None:
            weights = CASEWeightConfig()

        weight_dict = weights.as_dict()

        # Stage 0 (optional): Apply temporal decay
        decayed_profile: DecayAdjustedProfile | None = None
        effective_profile = profile

        if decay_engine is not None:
            decayed_profile = decay_engine.apply(profile)
            # Rebuild a SignalProfile with decay-adjusted confidences
            effective_profile = self._apply_decay_to_profile(
                profile, decayed_profile
            )

        # Stage 1: Normalize all signals
        normalized = self._normalize_signals(effective_profile)

        # Stage 2: Aggregate into category subscores
        subscores = self._aggregate_categories(normalized, effective_profile)

        # Stage 3: Detect and resolve conflicts
        subscores, conflict_list = self._resolve_conflicts(
            subscores, effective_profile
        )

        # Stage 4: Compute weighted final score
        raw_score, convergence_bonus = self._compute_weighted_score(
            subscores, weight_dict
        )

        # Apply cross-category conflict penalty
        conflict_penalty = max(0, len(conflict_list))
        if conflict_penalty > 0:
            penalty_factor = 1.0 - min(conflict_penalty, 2) * 0.10
            raw_score *= penalty_factor

        final_score = min(100.0, raw_score + convergence_bonus)
        final_score = round(max(0.0, final_score), 1)

        # Stage 5: Classify
        environment = self._classify(final_score)

        active_count = sum(
            1 for s in subscores.values() if s.fired > 0
        )

        # Extract decay metadata
        decay_applied = decayed_profile is not None
        avg_freshness = decayed_profile.average_freshness if decayed_profile else 1.0
        expired_count = decayed_profile.expired_signals if decayed_profile else 0
        freshness_lvl = decayed_profile.overall_freshness if decayed_profile else FreshnessLevel.FRESH

        logger.info(
            f"CASE: {profile.ticker} → score={final_score}, "
            f"env={environment.value}, active={active_count}"
            f"{f', freshness={avg_freshness:.3f}' if decay_applied else ''}"
        )

        return CompositeAlphaResult(
            ticker=profile.ticker,
            composite_alpha_score=final_score,
            signal_environment=environment,
            subscores={k: v for k, v in subscores.items()},
            active_categories=active_count,
            convergence_bonus=convergence_bonus,
            cross_category_conflicts=conflict_list,
            weight_profile=weight_dict,
            evaluated_at=datetime.now(timezone.utc),
            signal_profile=profile,
            decay_applied=decay_applied,
            average_freshness=round(avg_freshness, 4),
            expired_signal_count=expired_count,
            freshness_level=freshness_lvl,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # Stage 0: Decay Adjuster
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _apply_decay_to_profile(
        original: SignalProfile,
        decayed: DecayAdjustedProfile,
    ) -> SignalProfile:
        """
        Rebuild a SignalProfile with decay-adjusted confidences.

        Expired signals have their `fired` flag cleared so downstream stages
        ignore them.  Active signals have confidence scaled by decay_factor.
        """
        from copy import deepcopy

        adjusted_signals = []
        decay_map = {
            ds.signal_id: ds for ds in decayed.signals
        }

        for sig in original.signals:
            adj_sig = deepcopy(sig)
            ds = decay_map.get(sig.signal_id)

            if ds is not None and sig.fired:
                if ds.is_expired:
                    adj_sig.fired = False
                    adj_sig.confidence = 0.0
                else:
                    adj_sig.confidence = round(
                        sig.confidence * ds.decay_factor, 4
                    )

            adjusted_signals.append(adj_sig)

        fired_count = sum(1 for s in adjusted_signals if s.fired)

        return SignalProfile(
            ticker=original.ticker,
            evaluated_at=original.evaluated_at,
            total_signals=len(adjusted_signals),
            fired_signals=fired_count,
            signals=adjusted_signals,
            category_summary=original.category_summary,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # Stage 1: Normalizer
    # ═════════════════════════════════════════════════════════════════════════

    def _normalize_signals(
        self, profile: SignalProfile
    ) -> dict[str, list[tuple[EvaluatedSignal, float]]]:
        """
        Normalize each evaluated signal to a 0–100 score.

        Returns a dict keyed by category with lists of
        (EvaluatedSignal, normalized_score) tuples.

        If backtest data is available, applies quality-tier multipliers
        from the Signal Performance Database.
        """
        result: dict[str, list[tuple[EvaluatedSignal, float]]] = {}

        # Lazy-load dynamic weights from backtest evidence (cached)
        dynamic_weights = self._get_dynamic_weights()

        # Lazy-load crowding penalties (cached)
        crowding_penalties = self._get_crowding_penalties()

        for sig in profile.signals:
            cat_key = sig.category.value
            result.setdefault(cat_key, [])

            if not sig.fired or sig.value is None:
                result[cat_key].append((sig, 0.0))
                continue

            # Look up the definition to get thresholds
            sig_def = registry.get(sig.signal_id)
            if sig_def is None:
                result[cat_key].append((sig, 0.0))
                continue

            nss = self._compute_normalized_score(sig, sig_def)
            # Modulate by confidence and weight
            effective = nss * sig.confidence * sig_def.weight

            # Apply continuous dynamic weight from backtest evidence
            bt_multiplier = dynamic_weights.get(sig.signal_id, 1.0)
            effective *= bt_multiplier

            # Apply crowding penalty (reduces score for overcrowded signals)
            crowding_penalty = crowding_penalties.get(profile.ticker, 1.0)
            effective *= crowding_penalty

            result[cat_key].append((sig, effective))

        return result

    def _get_dynamic_weights(self) -> dict[str, float]:
        """
        Load continuous dynamic weights from the DynamicWeightEngine.

        Uses the P(s)×C(s)×R(s) formula where:
          P(s) = Performance Score (Sharpe + HitRate blend)
          C(s) = Confidence Score (sample size + p-value)
          R(s) = Recency Factor (exponential decay)

        Returns an empty dict (no-op) if no backtest data exists.
        """
        if not hasattr(self, "_weight_cache"):
            self._weight_cache: dict[str, float] = {}
        if self._weight_cache:
            return self._weight_cache

        try:
            from src.engines.backtesting.dynamic_weights import (
                DynamicWeightEngine,
            )
            engine = DynamicWeightEngine()
            self._weight_cache = engine.get_weight_dict()
        except Exception:
            # Graceful degradation: no backtest data → no modulation
            self._weight_cache = {}

        return self._weight_cache

    def _get_crowding_penalties(self) -> dict[str, float]:
        """
        Load crowding penalty factors from the CrowdingEngine.

        Penalty = 1.0 − (max_penalty × CRS), ranging [0.6, 1.0].

        Returns an empty dict (no-op) if no crowding data exists.
        """
        if not hasattr(self, "_crowding_cache"):
            self._crowding_cache: dict[str, float] = {}
        if self._crowding_cache:
            return self._crowding_cache

        try:
            from src.engines.crowding.engine import CrowdingEngine
            engine = CrowdingEngine()
            self._crowding_cache = engine.get_all_penalties()
        except Exception:
            # Graceful degradation: no crowding data → no penalty
            self._crowding_cache = {}

        return self._crowding_cache

    @staticmethod
    def _compute_normalized_score(
        sig: EvaluatedSignal,
        sig_def: AlphaSignalDefinition,
    ) -> float:
        """
        Compute the Normalized Signal Score (NSS) for a single signal.

        Maps the signal value to 0–100 based on how far it exceeds the
        threshold relative to the strong_threshold.
        """
        value = sig.value
        if value is None:
            return 0.0

        threshold = sig_def.threshold
        strong = sig_def.strong_threshold

        if sig_def.direction == SignalDirection.ABOVE:
            if strong is None:
                strong = threshold * 1.5 if threshold != 0 else 1.0
            span = strong - threshold
            if span <= 0:
                return 50.0 if value > threshold else 0.0
            ratio = (value - threshold) / span
            return max(0.0, min(100.0, ratio * 100.0))

        elif sig_def.direction == SignalDirection.BELOW:
            if strong is None:
                strong = threshold * 0.6 if threshold != 0 else -1.0
            span = threshold - strong  # positive span
            if span <= 0:
                return 50.0 if value < threshold else 0.0
            ratio = (threshold - value) / span
            return max(0.0, min(100.0, ratio * 100.0))

        elif sig_def.direction == SignalDirection.BETWEEN:
            upper = sig_def.upper_threshold or threshold
            lower = min(threshold, upper)
            upper = max(threshold, upper)
            mid = (lower + upper) / 2
            half_span = (upper - lower) / 2
            if half_span <= 0:
                return 50.0
            distance = abs(value - mid)
            ratio = 1.0 - (distance / half_span)
            return max(0.0, min(100.0, ratio * 100.0))

        return 0.0

    # ═════════════════════════════════════════════════════════════════════════
    # Stage 2: Category Aggregator
    # ═════════════════════════════════════════════════════════════════════════

    def _aggregate_categories(
        self,
        normalized: dict[str, list[tuple[EvaluatedSignal, float]]],
        profile: SignalProfile,
    ) -> dict[str, CategorySubscore]:
        """
        Aggregate normalized signal scores into per-category subscores.

        Uses a weighted fill ratio: sum of effective scores / sum of max
        possible weights, scaled to 0–100.
        """
        subscores: dict[str, CategorySubscore] = {}

        # Include all 8 categories even if no signals exist
        for cat in SignalCategory:
            cat_key = cat.value
            entries = normalized.get(cat_key, [])

            total = len(entries)
            fired_entries = [(s, score) for s, score in entries if s.fired]
            fired_count = len(fired_entries)

            if total == 0:
                subscores[cat_key] = CategorySubscore(
                    category=cat,
                    score=0.0,
                    fired=0,
                    total=0,
                    coverage=0.0,
                )
                continue

            # Sum of all enabled signal weights (max possible)
            max_weight_sum = 0.0
            for sig, _ in entries:
                sig_def = registry.get(sig.signal_id)
                max_weight_sum += sig_def.weight if sig_def else 1.0

            # Sum of effective scores
            effective_sum = sum(score for _, score in fired_entries)

            # Raw category score
            if max_weight_sum > 0:
                raw_score = (effective_sum / max_weight_sum) * 100.0
            else:
                raw_score = 0.0

            # Coverage penalty
            coverage = fired_count / total if total > 0 else 0.0
            if coverage < 0.3 and coverage > 0:
                raw_score *= coverage / 0.3

            raw_score = max(0.0, min(100.0, raw_score))

            # Top signals (by effective score, descending)
            sorted_fired = sorted(fired_entries, key=lambda x: x[1], reverse=True)
            top_names = [s.signal_name for s, _ in sorted_fired[:3]]

            subscores[cat_key] = CategorySubscore(
                category=cat,
                score=round(raw_score, 1),
                fired=fired_count,
                total=total,
                coverage=round(coverage, 3),
                top_signals=top_names,
            )

        return subscores

    # ═════════════════════════════════════════════════════════════════════════
    # Stage 3: Conflict Resolver
    # ═════════════════════════════════════════════════════════════════════════

    def _resolve_conflicts(
        self,
        subscores: dict[str, CategorySubscore],
        profile: SignalProfile,
    ) -> tuple[dict[str, CategorySubscore], list[str]]:
        """
        Detect and penalise contradictory signals.

        1. Intra-category: penalise categories with mixed-direction signals.
        2. Cross-category: detect correlated category conflicts.

        Returns the updated subscores and a list of conflict descriptions.
        """
        # ── Intra-category conflicts ─────────────────────────────────────
        for cat_key, subscore in subscores.items():
            if subscore.fired < 2:
                continue

            cat_signals = [
                s for s in profile.signals
                if s.category.value == cat_key and s.fired
            ]

            # Detect mixed directions by checking signal definitions
            directions: set[str] = set()
            for sig in cat_signals:
                sig_def = registry.get(sig.signal_id)
                if sig_def:
                    directions.add(sig_def.direction.value)

            if len(directions) > 1:
                # Mixed directions = conflict
                n_conflicting = len(cat_signals) // 2  # rough estimate
                penalty = 1.0 - (n_conflicting / len(cat_signals)) * 0.5
                penalty = max(0.5, penalty)  # floor at 50%

                subscore.conflict_detected = True
                subscore.conflict_penalty = round(penalty, 3)
                subscore.score = round(subscore.score * penalty, 1)

        # ── Cross-category conflicts ─────────────────────────────────────
        conflict_descriptions: list[str] = []

        for cat_a, cat_b, desc in _CROSS_CATEGORY_CONFLICTS:
            score_a = subscores.get(cat_a)
            score_b = subscores.get(cat_b)

            if score_a is None or score_b is None:
                continue
            if score_a.fired == 0 or score_b.fired == 0:
                continue

            # Conflict if both are active but in opposing directions
            # (high score in one + high score in the other, where the pair
            # represents a conceptual tension)
            if score_a.score >= 50 and score_b.score >= 50:
                conflict_descriptions.append(desc)

        return subscores, conflict_descriptions

    # ═════════════════════════════════════════════════════════════════════════
    # Stage 4: Weighted Scorer
    # ═════════════════════════════════════════════════════════════════════════

    def _compute_weighted_score(
        self,
        subscores: dict[str, CategorySubscore],
        weights: dict[str, float],
    ) -> tuple[float, float]:
        """
        Apply category weights and compute the final composite score.

        Returns (raw_score, convergence_bonus).
        """
        weighted_sum = 0.0
        for cat_key, weight in weights.items():
            subscore = subscores.get(cat_key)
            if subscore is not None:
                weighted_sum += subscore.score * weight

        # Convergence bonus
        active_count = sum(1 for s in subscores.values() if s.fired > 0)
        bonus = 0.0
        if active_count >= 7:
            bonus = _CONVERGENCE_BONUS_7
        elif active_count >= 5:
            bonus = _CONVERGENCE_BONUS_5

        return weighted_sum, bonus

    # ═════════════════════════════════════════════════════════════════════════
    # Stage 5: Classifier
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _classify(score: float) -> SignalEnvironment:
        """Map a 0–100 composite score to a semantic environment label."""
        if score >= 80:
            return SignalEnvironment.VERY_STRONG
        elif score >= 60:
            return SignalEnvironment.STRONG
        elif score >= 40:
            return SignalEnvironment.NEUTRAL
        elif score >= 20:
            return SignalEnvironment.WEAK
        else:
            return SignalEnvironment.NEGATIVE
