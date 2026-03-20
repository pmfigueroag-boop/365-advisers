"""
src/engines/alpha_signals/combiner.py
──────────────────────────────────────────────────────────────────────────────
Combines per-category signal scores into an overall CompositeScore.

V2 (AVS-validated, Mar 2026):
  - IC-weighted scoring: signals weight by their validated IC (not arbitrary)
  - Contrarian alpha: death_cross/deep_pullback CONTRIBUTE positively
  - Redundancy control: correlated signals de-weighted (pe_low ≈ ebit_ev)
  - No breadth bonus (v1 breadth bonus rewarded buying at tops)

V1 Problems (identified by AVS Phase 1):
  - Mean-strength + breadth bonus → high scores at market tops
  - Composite score INVERSELY correlated with forward returns
  - 0.0-0.2 bucket returned +3.89% vs 0.35-0.5 bucket +1.67%
"""

from __future__ import annotations

from src.engines.alpha_signals.models import (
    SignalProfile,
    CompositeScore,
    CategoryScore,
    SignalCategory,
    ConfidenceLevel,
    EvaluatedSignal,
)


# ── AVS-validated IC weights (from Phase 0 IC Screen, Mar 2026) ──────────────
# These are the Spearman IC_20d values from the validation run.
# Positive IC = signal correctly predicts positive forward returns.
# For bearish/risk signals with positive IC, we treat their fire as a
# CONTRARIAN BUY signal (death_cross fires → buy).

_IC_WEIGHTS: dict[str, float] = {
    # Contrarian signals (fire = contrarian buy opportunity)
    "risk.death_cross": 0.26,            # IC=+0.26, strongest signal
    "pricecycle.deep_pullback": 0.18,    # IC=+0.18
    "pricecycle.oversold_z": 0.08,       # IC=+0.08

    # Value signals
    "value.ev_ebitda_low": 0.11,         # IC=+0.11
    "value.div_yield_vs_hist": 0.11,     # IC=+0.11 (redundant with ev_ebitda_low → de-weight)
    "value.pe_low": 0.08,               # IC=+0.08
    "value.ebit_ev_high": 0.04,          # IC=+0.08 but ρ=1.0 with pe_low → halved
    "value.shareholder_yield": 0.06,     # IC=+0.06

    # Volume/flow signals
    "momentum.volume_surge": 0.05,       # IC=+0.05
    "flow.unusual_volume": 0.05,         # IC=+0.05
    "flow.volume_price_divergence": 0.05,# IC=+0.05

    # Momentum (moderate positive)
    "momentum.rsi_bullish": 0.03,        # IC=+0.03

    # Inverse predictors → SUBTRACT from score when they fire
    "momentum.golden_cross": -0.10,      # IC=-0.23, hurts when active
    "momentum.price_above_ema20": -0.05, # IC=-0.14
    "momentum.adx_trend_strength": -0.05,# IC=-0.13

    # Quality (slight negative IC — don't reward these)
    "quality.high_roic": 0.0,            # IC=-0.02
    "quality.high_roe": 0.0,             # IC=-0.02
    "quality.low_leverage": 0.0,         # IC=-0.02
    "quality.asset_turnover_improving": -0.03, # IC=-0.08
}

# Redundancy clusters: only count the best signal from each cluster
_REDUNDANCY_CLUSTERS: list[set[str]] = [
    {"value.pe_low", "value.ebit_ev_high"},            # ρ=1.000
    {"value.ev_ebitda_low", "value.div_yield_vs_hist"}, # ρ=0.999
    {"quality.high_roic", "quality.high_roe"},          # ρ=0.995
    {"momentum.volume_surge", "flow.unusual_volume", "flow.volume_price_divergence"},  # ρ>0.8
]

# Default weight for signals not in the IC table
_DEFAULT_IC_WEIGHT = 0.0


class SignalCombiner:
    """
    V2: IC-weighted signal combiner.

    Instead of rewarding breadth (how many categories fire), this combiner
    weights each signal by its validated IC and sums the contributions.

    Key innovation: contrarian signals (death_cross, deep_pullback)
    CONTRIBUTE POSITIVELY when fired, rather than being treated as risk.

    Usage::

        combiner = SignalCombiner()
        composite = combiner.combine(profile)
    """

    def combine(self, profile: SignalProfile) -> CompositeScore:
        """
        Compute IC-weighted composite score.

        1. For each fired signal, add IC_weight × confidence
        2. De-duplicate redundant signals (keep best from each cluster)
        3. Normalize to [0, 1]
        4. Determine dominant category and confidence
        """
        cat_scores = profile.category_summary
        if not cat_scores:
            return CompositeScore()

        fired = [s for s in profile.signals if s.fired]
        if not fired:
            return CompositeScore(
                overall_strength=0.0,
                overall_confidence=ConfidenceLevel.LOW,
                category_scores=cat_scores,
                multi_category_bonus=False,
                dominant_category=None,
                active_categories=0,
            )

        # ── De-duplicate redundant signals ────────────────────────────────
        active_ids = {s.signal_id for s in fired}
        suppressed: set[str] = set()

        for cluster in _REDUNDANCY_CLUSTERS:
            cluster_active = cluster & active_ids
            if len(cluster_active) > 1:
                # Keep the one with highest IC weight
                best = max(cluster_active, key=lambda sid: abs(_IC_WEIGHTS.get(sid, 0)))
                suppressed |= cluster_active - {best}

        # ── Compute IC-weighted score ─────────────────────────────────────
        raw_score = 0.0
        max_possible = 0.0
        category_contributions: dict[str, float] = {}

        for sig in profile.signals:
            ic_w = _IC_WEIGHTS.get(sig.signal_id, _DEFAULT_IC_WEIGHT)

            if ic_w > 0:
                max_possible += ic_w  # Maximum if all positive signals fire

            if sig.signal_id in suppressed:
                continue  # Skip redundant

            if sig.fired and ic_w != 0:
                contribution = ic_w * sig.confidence
                raw_score += contribution

                # Track per-category contributions
                cat_key = sig.category.value
                category_contributions[cat_key] = (
                    category_contributions.get(cat_key, 0.0) + contribution
                )
            elif not sig.fired and ic_w < 0:
                # Inverse signal NOT firing = good
                pass  # No contribution

        # ── Normalize ─────────────────────────────────────────────────────
        if max_possible > 0:
            normalized = max(0.0, min(1.0, raw_score / max_possible))
        else:
            normalized = 0.0

        # ── Dominant and active categories ────────────────────────────────
        active = {k: v for k, v in cat_scores.items() if v.fired > 0}
        active_count = len(active)

        dominant_category = None
        if category_contributions:
            dominant_key = max(
                category_contributions,
                key=lambda k: abs(category_contributions[k]),
            )
            try:
                dominant_category = SignalCategory(dominant_key)
            except ValueError:
                pass

        # ── Confidence ────────────────────────────────────────────────────
        if normalized >= 0.5 and active_count >= 2:
            confidence = ConfidenceLevel.HIGH
        elif normalized >= 0.3 or active_count >= 2:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

        # Note: no breadth bonus in v2 (AVS proved breadth → overfit)
        return CompositeScore(
            overall_strength=round(normalized, 3),
            overall_confidence=confidence,
            category_scores=cat_scores,
            multi_category_bonus=False,  # Removed in v2
            dominant_category=dominant_category,
            active_categories=active_count,
        )
