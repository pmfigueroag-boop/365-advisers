"""
src/engines/alpha_decay/engine.py
──────────────────────────────────────────────────────────────────────────────
Core Decay Engine — applies temporal decay to a SignalProfile, producing
a DecayAdjustedProfile where signal strengths reflect their age.

The engine sits between the SignalEvaluator and the Composite Alpha Engine:

    SignalProfile  →  DecayEngine.apply()  →  DecayAdjustedProfile  →  CASE
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from src.engines.alpha_signals.models import (
    EvaluatedSignal,
    SignalCategory,
    SignalProfile,
)
from src.engines.alpha_decay.models import (
    CategoryDecaySummary,
    DecayAdjustedProfile,
    DecayAdjustedSignal,
    DecayConfig,
    FreshnessLevel,
)
from src.engines.alpha_decay.tracker import ActivationTracker

logger = logging.getLogger("365advisers.alpha_decay.engine")


class DecayEngine:
    """
    Stateless engine that applies temporal decay to signal profiles.

    Usage::

        tracker = ActivationTracker()
        engine  = DecayEngine(tracker)
        decayed = engine.apply(signal_profile)
    """

    def __init__(
        self,
        tracker: ActivationTracker,
        config: DecayConfig | None = None,
    ) -> None:
        self._tracker = tracker
        self._config = config or DecayConfig()

    @property
    def config(self) -> DecayConfig:
        return self._config

    # ── Public API ────────────────────────────────────────────────────────

    def apply(
        self,
        profile: SignalProfile,
        reference_time: datetime | None = None,
    ) -> DecayAdjustedProfile:
        """
        Apply temporal decay to all signals in a SignalProfile.

        Parameters
        ----------
        profile : SignalProfile
            Raw evaluated signal profile from the SignalEvaluator.
        reference_time : datetime | None
            Time to measure signal age against.  Defaults to now (UTC).

        Returns
        -------
        DecayAdjustedProfile
            Profile with decay-adjusted signal strengths and freshness.
        """
        if not self._config.enabled:
            # Bypass: return profile wrapped as DecayAdjustedProfile with no decay
            return self._passthrough(profile)

        now = reference_time or datetime.now(timezone.utc)

        # Step 1: Update activation tracker with current signal state
        self._tracker.update_activations(profile)

        # Step 2: Apply decay to each signal
        decayed_signals: list[DecayAdjustedSignal] = []
        for sig in profile.signals:
            decayed = self._decay_signal(sig, profile.ticker, now)
            decayed_signals.append(decayed)

        # Step 3: Build category summaries
        category_summary = self._build_category_summary(decayed_signals)

        # Step 4: Compute overall freshness
        fired_decayed = [s for s in decayed_signals if s.fired or s.is_expired]
        if fired_decayed:
            avg_freshness = sum(s.decay_factor for s in fired_decayed) / len(fired_decayed)
        else:
            avg_freshness = 1.0

        active = sum(1 for s in decayed_signals if s.fired)
        expired = sum(1 for s in decayed_signals if s.is_expired)

        overall_freshness = self._classify_freshness(avg_freshness)

        logger.info(
            f"DECAY: {profile.ticker} → active={active}, expired={expired}, "
            f"freshness={avg_freshness:.3f} ({overall_freshness.value})"
        )

        return DecayAdjustedProfile(
            ticker=profile.ticker,
            evaluated_at=now,
            total_signals=len(decayed_signals),
            active_signals=active,
            expired_signals=expired,
            signals=decayed_signals,
            category_summary=category_summary,
            average_freshness=round(avg_freshness, 4),
            overall_freshness=overall_freshness,
            decay_config=self._config,
        )

    # ── Private helpers ───────────────────────────────────────────────────

    def _decay_signal(
        self,
        sig: EvaluatedSignal,
        ticker: str,
        now: datetime,
    ) -> DecayAdjustedSignal:
        """Apply decay to a single evaluated signal."""
        if not sig.fired:
            # Non-fired signals: no decay to apply
            return DecayAdjustedSignal.from_evaluated(
                sig,
                age_days=0.0,
                half_life=self._config.get_half_life(sig.category),
                decay_factor=1.0,
                expiration_threshold=self._config.expiration_threshold,
            )

        # Look up activation timestamp
        activation = self._tracker.get_activation(sig.signal_id, ticker)
        if activation is None:
            # First-time fire: no decay yet
            age_days = 0.0
            decay_factor = 1.0
        else:
            # Compute age in days (ensure both are tz-aware)
            act_time = activation.activated_at
            ref_time = now
            # Normalize timezone awareness
            if act_time.tzinfo is None:
                act_time = act_time.replace(tzinfo=timezone.utc)
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=timezone.utc)
            delta = ref_time - act_time
            age_days = max(0.0, delta.total_seconds() / 86400.0)

            # Compute decay
            decay_factor = self._compute_decay(sig.category, age_days)

        half_life = self._config.get_half_life(sig.category)

        return DecayAdjustedSignal.from_evaluated(
            sig,
            age_days=age_days,
            half_life=half_life,
            decay_factor=decay_factor,
            expiration_threshold=self._config.expiration_threshold,
        )

    def _compute_decay(self, category: SignalCategory, age_days: float) -> float:
        """
        Compute the decay factor for a signal.

        Exponential: decay = e^(-λ·t)   where λ = ln(2) / half_life
        """
        if age_days <= 0:
            return 1.0

        lam = self._config.get_lambda(category)
        if lam <= 0:
            return 1.0

        decay = math.exp(-lam * age_days)
        return max(0.0, min(1.0, decay))

    def _build_category_summary(
        self,
        signals: list[DecayAdjustedSignal],
    ) -> dict[str, CategoryDecaySummary]:
        """Aggregate per-category decay statistics."""
        categories: dict[str, list[DecayAdjustedSignal]] = {}
        for sig in signals:
            key = sig.category.value
            categories.setdefault(key, []).append(sig)

        summary: dict[str, CategoryDecaySummary] = {}
        for cat_key, cat_signals in categories.items():
            active = [s for s in cat_signals if s.fired]
            expired = [s for s in cat_signals if s.is_expired]
            all_relevant = active + expired

            if all_relevant:
                avg_decay = sum(s.decay_factor for s in all_relevant) / len(all_relevant)
            else:
                avg_decay = 1.0

            summary[cat_key] = CategoryDecaySummary(
                category=SignalCategory(cat_key),
                active_signals=len(active),
                expired_signals=len(expired),
                total_signals=len(cat_signals),
                average_decay_factor=round(avg_decay, 4),
                freshness=self._classify_freshness(avg_decay),
            )

        return summary

    @staticmethod
    def _classify_freshness(decay_factor: float) -> FreshnessLevel:
        """Map a decay factor to a semantic freshness label."""
        if decay_factor >= 0.80:
            return FreshnessLevel.FRESH
        elif decay_factor >= 0.50:
            return FreshnessLevel.AGING
        elif decay_factor >= 0.20:
            return FreshnessLevel.STALE
        else:
            return FreshnessLevel.EXPIRED

    def _passthrough(self, profile: SignalProfile) -> DecayAdjustedProfile:
        """Create a DecayAdjustedProfile with no decay applied."""
        signals = [
            DecayAdjustedSignal.from_evaluated(
                sig,
                age_days=0.0,
                half_life=self._config.get_half_life(sig.category),
                decay_factor=1.0,
                expiration_threshold=self._config.expiration_threshold,
            )
            for sig in profile.signals
        ]

        category_summary = self._build_category_summary(signals)

        return DecayAdjustedProfile(
            ticker=profile.ticker,
            evaluated_at=profile.evaluated_at,
            total_signals=profile.total_signals,
            active_signals=profile.fired_signals,
            expired_signals=0,
            signals=signals,
            category_summary=category_summary,
            average_freshness=1.0,
            overall_freshness=FreshnessLevel.FRESH,
            decay_config=self._config,
        )
