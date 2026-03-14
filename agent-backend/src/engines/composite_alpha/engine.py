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
    # P1 fix T3: expanded conflict pairs
    ("momentum", "value", "Momentum vs Value: high momentum ignoring stretched valuation"),
    ("quality", "event", "Quality vs Event: quality degradation event detected"),
    ("growth", "volatility", "Growth vs Volatility: high-growth with elevated vol risk"),
    ("flow", "value", "Flow vs Value: flow signals conflicting with valuation"),
    ("momentum", "macro", "Momentum vs Macro: strong momentum against macro headwinds"),
]

# ── Convergence bonus thresholds ─────────────────────────────────────────────

_CONVERGENCE_BONUS_5 = 3.0   # +3 when >= 5 active categories
_CONVERGENCE_BONUS_7 = 5.0   # +5 when >= 7 active categories

# ── Spread amplifier (P0 fix: widen narrow score clustering) ─────────────
_SPREAD_FACTOR = 1.4          # Push scores 40% away from midpoint
_SPREAD_MIDPOINT = 50.0

# ── Regime multipliers (P0 fix: market-awareness) ────────────────────────
_REGIME_MULTIPLIER = {
    "bullish": 1.10,   # Boost 10% in risk-on
    "neutral": 1.00,
    "bearish": 0.80,   # Discount 20% in risk-off
}


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
        data_age_hours: float | None = None,
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

        # Stage 5: Spread amplification (P0 fix C2)
        diff = final_score - _SPREAD_MIDPOINT
        final_score = _SPREAD_MIDPOINT + diff * _SPREAD_FACTOR
        final_score = round(max(0.0, min(100.0, final_score)), 1)

        # Stage 6: Market regime adjustment (P0 fix C1)
        regime = self._detect_market_regime()
        regime_mult = _REGIME_MULTIPLIER.get(regime, 1.0)
        if regime_mult != 1.0:
            final_score = round(max(0.0, min(100.0, final_score * regime_mult)), 1)

        # Stage 6b: Data Freshness Penalty
        # Penalise scores based on stale underlying data. Uses exponential
        # decay with half-life of 90 days (2160 hours).
        # - Fresh (<24h): no penalty
        # - 30 days: ~80% retained
        # - 90 days: ~50% retained
        # - 180 days: ~25% retained
        freshness_discount = 1.0
        if data_age_hours is not None and data_age_hours > 24.0:
            import math
            half_life_hours = 2160.0  # 90 days
            freshness_discount = math.pow(0.5, data_age_hours / half_life_hours)
            freshness_discount = max(0.25, freshness_discount)  # Floor at 25%
            final_score *= freshness_discount
            final_score = round(max(0.0, min(100.0, final_score)), 1)

        # Stage 7: Classify
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
            f"env={environment.value}, active={active_count}, "
            f"regime={regime}"
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

            # P0 fix C3: Risk signals contribute NEGATIVELY
            is_risk = "risk" in sig_def.tags if sig_def.tags else False
            if is_risk:
                effective = -effective  # Invert to pull score down

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

        Also applies degradation penalties from the QVF: signals
        flagged as degraded get their weights automatically reduced.

        Returns an empty dict (no-op) if no backtest data exists.
        Cache expires after 300 seconds.
        """
        import time

        if not hasattr(self, "_weight_cache"):
            self._weight_cache: dict[str, float] = {}
            self._weight_cache_ts: float = 0.0

        # TTL check (300s = 5 min)
        now = time.monotonic()
        if self._weight_cache and (now - self._weight_cache_ts) < 300.0:
            return self._weight_cache

        self._weight_cache = {}
        self._weight_cache_ts = now

        try:
            from src.engines.backtesting.dynamic_weights import (
                DynamicWeightEngine,
            )
            engine = DynamicWeightEngine()
            self._weight_cache = engine.get_weight_dict()
        except Exception:
            # Graceful degradation: no backtest data → no modulation
            self._weight_cache = {}

        # Apply degradation penalties from QVF
        try:
            from src.data.database import DegradationAlertRecord, SessionLocal
            with SessionLocal() as db:
                active_alerts = (
                    db.query(DegradationAlertRecord)
                    .filter(DegradationAlertRecord.resolved_at.is_(None))
                    .all()
                )
                for alert in active_alerts:
                    sid = alert.signal_id
                    if alert.recommendation == "reduce_weight":
                        # Apply 50% penalty for degraded signals
                        current = self._weight_cache.get(sid, 1.0)
                        self._weight_cache[sid] = current * 0.5
                    elif alert.recommendation == "disable":
                        # Near-zero weight for severely degraded
                        self._weight_cache[sid] = 0.05
        except Exception:
            # Graceful degradation: no alerts → no penalty
            pass

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
            # S3: Sigmoid normalization — k=5.0 calibrated so that:
            #   ratio=0.0 (at threshold) → ~7%  (barely fires)
            #   ratio=0.5 (midpoint)     → ~50% (moderate signal)
            #   ratio=1.0 (at strong)    → ~93% (strong signal)
            #   ratio>1.5                → ~99% (diminishing returns)
            import math
            return max(0.0, min(100.0, 100.0 / (1.0 + math.exp(-5.0 * (ratio - 0.5)))))

        elif sig_def.direction == SignalDirection.BELOW:
            if strong is None:
                strong = threshold * 0.6 if threshold != 0 else -1.0
            span = threshold - strong  # positive span
            if span <= 0:
                return 50.0 if value < threshold else 0.0
            ratio = (threshold - value) / span
            # P1 fix T1: sigmoid normalization
            import math
            return max(0.0, min(100.0, 100.0 / (1.0 + math.exp(-5.0 * (ratio - 0.5)))))

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

            # Sum of effective scores with P1 redundancy discount:
            # When >2 signals fire in a category, apply √n diminishing
            # returns to prevent correlated signals inflating the score.
            scores = [score for _, score in fired_entries]
            if len(scores) <= 2:
                effective_sum = sum(scores)
            else:
                # Sort descending, first 2 count fully, rest diminished
                scores.sort(reverse=True)
                effective_sum = sum(scores[:2])
                for i, s in enumerate(scores[2:], start=1):
                    effective_sum += s / (i + 1) ** 0.5  # √(n) discount

            # Raw category score
            if max_weight_sum > 0:
                raw_score = (effective_sum / max_weight_sum) * 100.0
            else:
                raw_score = 0.0

            # Coverage penalty
            coverage = fired_count / total if total > 0 else 0.0
            # S3: Smooth sigmoid coverage penalty — k=10.0, midpoint=0.25
            #   coverage=0.0  → factor ~0.08 (almost no signal coverage)
            #   coverage=0.25 → factor ~0.50 (midpoint — typical for most categories)
            #   coverage=0.50 → factor ~0.92 (good coverage)
            #   coverage=1.0  → factor ~1.0  (full coverage)
            import math
            coverage_factor = 1.0 / (1.0 + math.exp(-10.0 * (coverage - 0.25)))
            raw_score *= coverage_factor

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

        # ── Cross-category conflicts (direction-aware) ───────────────────────
        conflict_descriptions: list[str] = []

        # Build per-category direction from signal definitions
        category_direction: dict[str, str] = {}  # "bullish", "bearish", "mixed"
        for sig in profile.signals:
            if not sig.fired:
                continue
            cat_key = sig.category.value
            sig_def = registry.get(sig.signal_id)
            if sig_def is None:
                continue
            # Determine signal polarity from its direction
            if sig_def.direction == SignalDirection.ABOVE:
                polarity = "bullish"
            elif sig_def.direction == SignalDirection.BELOW:
                polarity = "bearish"
            else:
                polarity = "neutral"

            existing = category_direction.get(cat_key)
            if existing is None:
                category_direction[cat_key] = polarity
            elif existing != polarity and polarity != "neutral":
                category_direction[cat_key] = "mixed"

        for cat_a, cat_b, desc in _CROSS_CATEGORY_CONFLICTS:
            dir_a = category_direction.get(cat_a)
            dir_b = category_direction.get(cat_b)

            if dir_a is None or dir_b is None:
                continue

            # Conflict when categories have opposing directions
            # or when both are active with high scores (conceptual tension)
            opposing = (
                (dir_a == "bullish" and dir_b == "bearish")
                or (dir_a == "bearish" and dir_b == "bullish")
            )
            both_high = (
                subscores.get(cat_a, CategorySubscore(category=SignalCategory.VALUE)).score >= 50
                and subscores.get(cat_b, CategorySubscore(category=SignalCategory.VALUE)).score >= 50
                and dir_a == "mixed" or dir_b == "mixed"
            )

            if opposing or both_high:
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

        # P1 fix C5: quality-weighted convergence (only meaningful categories count)
        meaningful_active = sum(
            1 for s in subscores.values() if s.fired > 0 and s.score >= 40.0
        )
        bonus = 0.0
        if meaningful_active >= 7:
            bonus = _CONVERGENCE_BONUS_7
        elif meaningful_active >= 5:
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

    # ═════════════════════════════════════════════════════════════════════════
    # Stage 6: Market Regime Detector (P0 fix C1)
    # ═════════════════════════════════════════════════════════════════════════

    # Class-level cache for regime detection (avoid repeated API calls)
    _regime_cache: str | None = None
    _regime_cache_ts: float = 0.0
    _REGIME_TTL = 3600.0  # 1 hour

    def _detect_market_regime(self) -> str:
        """
        Detect broad market regime using SPY's SMA50/SMA200 relationship.

        Returns 'bullish', 'bearish', or 'neutral'.
        Cached for 1 hour to avoid API overhead.
        """
        import time as _t

        now = _t.monotonic()
        if (
            CompositeAlphaEngine._regime_cache is not None
            and (now - CompositeAlphaEngine._regime_cache_ts) < self._REGIME_TTL
        ):
            return CompositeAlphaEngine._regime_cache

        regime = "neutral"
        try:
            import yfinance as yf
            spy = yf.Ticker("SPY")
            hist = spy.history(period="1y")

            if hist is not None and len(hist) >= 200:
                sma_50 = hist["Close"].rolling(50).mean().iloc[-1]
                sma_200 = hist["Close"].rolling(200).mean().iloc[-1]
                current_price = hist["Close"].iloc[-1]

                if sma_50 > sma_200 and current_price > sma_50:
                    regime = "bullish"
                elif sma_50 < sma_200 and current_price < sma_50:
                    regime = "bearish"
                else:
                    regime = "neutral"

                logger.info(
                    f"REGIME: SPY price={current_price:.1f}, "
                    f"SMA50={sma_50:.1f}, SMA200={sma_200:.1f} → {regime}"
                )

        except Exception as exc:
            logger.warning(f"REGIME: detection failed, defaulting to neutral: {exc}")

        CompositeAlphaEngine._regime_cache = regime
        CompositeAlphaEngine._regime_cache_ts = now
        return regime
