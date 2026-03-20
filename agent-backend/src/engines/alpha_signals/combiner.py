"""
src/engines/alpha_signals/combiner.py
──────────────────────────────────────────────────────────────────────────────
Combines per-category signal scores into an overall CompositeScore.

V3 (Sector-Adaptive, Mar 2026):
  - Dual IC tables: tech vs non-tech (validated separately via AVS Phase 0)
  - Sector routing: combine() accepts sector parameter
  - 10+ signals flip sign between sectors (e.g. operating_leverage:
    tech IC=-0.18, non-tech IC=+0.19) → now correctly weighted
  - Preserves 2-level buy system (STRONG_BUY / BUY / HOLD)

V2 improvements retained:
  - IC-weighted scoring (not arbitrary weights)
  - Contrarian alpha: death_cross/deep_pullback CONTRIBUTE positively
  - Redundancy control: correlated signals de-weighted
  - No breadth bonus
"""

from __future__ import annotations

from src.engines.alpha_signals.models import (
    SignalProfile,
    CompositeScore,
    CategoryScore,
    SignalCategory,
    SignalLevel,
    ConfidenceLevel,
    EvaluatedSignal,
)


# ── Sector-Adaptive IC weights (from Phase 0 per-sector IC screens) ──────────
# Each table maps signal_id → IC_20d weight.
# Signals with |IC| < 0.005 are set to 0.0 (no contribution).

_IC_WEIGHTS_TECH: dict[str, float] = {
    # ── Strong positive (contrarian + value) ─────────────────────────
    "risk.death_cross": 0.26,            # IC=+0.26
    "pricecycle.deep_pullback": 0.18,    # IC=+0.18
    "value.ev_revenue_low": 0.16,        # IC=+0.16
    "value.ev_ebitda_low": 0.11,         # IC=+0.11
    "value.div_yield_vs_hist": 0.05,     # IC=+0.11 (de-weighted: ρ≈1 w/ ev_ebitda)
    "value.pe_low": 0.08,               # IC=+0.08
    "value.ebit_ev_high": 0.04,          # IC=+0.08 (de-weighted: ρ=1 w/ pe_low)
    "quality.piotroski_f_score": 0.08,   # IC=+0.08
    "pricecycle.oversold_z": 0.08,       # IC=+0.08
    "value.shareholder_yield": 0.06,     # IC=+0.06
    "momentum.volume_surge": 0.05,       # IC=+0.05
    "flow.unusual_volume": 0.05,         # IC=+0.05
    "flow.volume_price_divergence": 0.05,# IC=+0.05
    "momentum.rsi_bullish": 0.03,        # IC=+0.03

    # ── Near-zero / neutral ──────────────────────────────────────────
    "event.high_beta_sector": 0.0,
    "risk.high_beta": 0.0,
    "risk.pe_expensive": 0.0,
    "risk.macd_bearish": 0.0,
    "quality.high_roic": 0.0,
    "quality.high_roe": 0.0,
    "quality.low_leverage": 0.0,
    "risk.high_leverage": 0.0,

    # ── Inverse predictors (SUBTRACT when fired) ─────────────────────
    "flow.dark_pool_absorption": -0.02,
    "risk.ev_ebitda_expensive": -0.02,
    "growth.rule_of_40": -0.04,
    "value.fcf_yield_high": -0.05,
    "pricecycle.near_52w_high_risk": -0.05,
    "fundmom.margin_expanding": -0.05,
    "flow.mfi_oversold": -0.05,
    "quality.asset_turnover_improving": -0.06,
    "volatility.realized_vol_regime": -0.06,
    "growth.capex_intensity": -0.06,
    "quality.interest_coverage_fortress": -0.08,
    "quality.stable_margins": -0.12,
    "risk.revenue_decline": -0.12,
    "risk.earnings_decline": -0.12,
    "momentum.adx_trend_strength": -0.13,
    "momentum.price_above_ema20": -0.14,
    "value.peg_low": -0.15,
    "event.earnings_surprise": -0.15,
    "event.revenue_acceleration": -0.16,
    "growth.operating_leverage": -0.18,  # ⚡ FLIPS in non-tech!
    "momentum.golden_cross": -0.23,
}

_IC_WEIGHTS_NON_TECH: dict[str, float] = {
    # ── Strong positive ──────────────────────────────────────────────
    "growth.operating_leverage": 0.19,   # ⚡ FLIPPED from tech (-0.18)!
    "risk.high_leverage": 0.12,          # non-tech only alpha
    "risk.death_cross": 0.10,
    "risk.macd_bearish": 0.10,
    "risk.revenue_decline": 0.09,        # ⚡ FLIPPED from tech (-0.12)!
    "growth.capex_intensity": 0.09,      # ⚡ FLIPPED from tech (-0.06)!
    "fundmom.margin_expanding": 0.08,    # ⚡ FLIPPED from tech (-0.05)!
    "value.shareholder_yield": 0.08,
    "event.earnings_surprise": 0.08,     # ⚡ FLIPPED from tech (-0.15)!
    "value.div_yield_vs_hist": 0.08,
    "quality.interest_coverage_fortress": 0.08,  # ⚡ FLIPPED from tech (-0.08)!
    "risk.negative_margin": 0.07,
    "momentum.adx_trend_strength": 0.06, # ⚡ FLIPPED from tech (-0.13)!
    "risk.earnings_decline": 0.05,       # ⚡ FLIPPED from tech (-0.12)!
    "value.pb_low": 0.04,               # non-tech only
    "pricecycle.deep_pullback": 0.04,
    "quality.high_roe": 0.04,
    "flow.unusual_volume": 0.03,
    "pricecycle.oversold_z": 0.03,
    "quality.low_leverage": 0.03,
    "flow.volume_price_divergence": 0.02,
    "flow.mfi_oversold": 0.02,

    # ── Near-zero / neutral ──────────────────────────────────────────
    "quality.piotroski_f_score": 0.01,
    "momentum.rsi_bullish": 0.0,
    "quality.asset_turnover_improving": 0.0,
    "momentum.volume_surge": 0.0,
    "event.high_beta_sector": 0.0,
    "risk.high_beta": 0.0,
    "value.ev_ebitda_low": 0.0,          # IC≈0 in non-tech (was +0.11 in tech)
    "value.pe_low": 0.0,
    "value.peg_low": 0.0,
    "momentum.golden_cross": 0.0,        # IC≈0 in non-tech (was -0.23 in tech)

    # ── Inverse predictors ───────────────────────────────────────────
    "value.ebit_ev_high": -0.01,         # was +0.08 in tech!
    "event.revenue_acceleration": -0.02,
    "value.ev_revenue_low": -0.02,       # was +0.16 in tech!
    "risk.ev_ebitda_expensive": -0.02,
    "quality.stable_margins": -0.02,
    "pricecycle.stretched_above_mean": -0.04,
    "flow.dark_pool_absorption": -0.04,
    "quality.high_roic": -0.05,
    "momentum.price_above_ema20": -0.05,
    "pricecycle.near_52w_high_risk": -0.05,
    "value.fcf_yield_high": -0.06,
    "volatility.realized_vol_regime": -0.06,
    "risk.rsi_overbought": -0.07,
    "risk.pe_expensive": -0.08,
    "growth.rule_of_40": -0.10,
    "momentum.macd_bullish": -0.10,
}

# Redundancy clusters (shared across sectors)
_REDUNDANCY_CLUSTERS: list[set[str]] = [
    {"value.pe_low", "value.ebit_ev_high"},
    {"value.ev_ebitda_low", "value.div_yield_vs_hist"},
    {"quality.high_roic", "quality.high_roe"},
    {"momentum.volume_surge", "flow.unusual_volume", "flow.volume_price_divergence"},
    {"risk.revenue_decline", "risk.earnings_decline"},
    {"value.peg_low", "event.earnings_surprise"},
]

_DEFAULT_IC_WEIGHT = 0.0

# ── 2-Level Buy Thresholds ───────────────────────────────────────────────────
STRONG_BUY_THRESHOLD = 0.35
BUY_THRESHOLD = 0.20

# ── Sector classification ────────────────────────────────────────────────────
_TECH_SECTORS = {
    "technology", "communication services", "consumer cyclical",
    "information technology", "communication",
}


def _classify_sector(sector: str) -> str:
    """Classify a sector string into 'tech' or 'non_tech'."""
    if not sector:
        return "tech"  # Default fallback
    return "tech" if sector.strip().lower() in _TECH_SECTORS else "non_tech"


class SignalCombiner:
    """
    V3: Sector-adaptive IC-weighted signal combiner.

    Selects IC weight table based on sector classification:
      - Tech → _IC_WEIGHTS_TECH
      - Non-Tech → _IC_WEIGHTS_NON_TECH

    2-Level Buy System:
      - STRONG_BUY: composite_score > 0.35
      - BUY:        composite_score > 0.20
      - HOLD:       composite_score <= 0.20

    Usage::

        combiner = SignalCombiner()
        composite = combiner.combine(profile, sector="Technology")
    """

    def combine(
        self,
        profile: SignalProfile,
        sector: str = "",
    ) -> CompositeScore:
        """
        Compute sector-adaptive IC-weighted composite score.

        Args:
            profile: Evaluated signal profile for an asset.
            sector: Sector string (e.g. "Technology", "Healthcare").
                    Used to select the appropriate IC weight table.
        """
        cat_scores = profile.category_summary
        if not cat_scores:
            return CompositeScore()

        fired = [s for s in profile.signals if s.fired]
        if not fired:
            return CompositeScore(
                overall_strength=0.0,
                overall_confidence=ConfidenceLevel.LOW,
                signal_level=SignalLevel.HOLD,
                category_scores=cat_scores,
                multi_category_bonus=False,
                dominant_category=None,
                active_categories=0,
            )

        # ── Select sector-appropriate IC table ────────────────────────────
        sector_class = _classify_sector(sector)
        ic_weights = (
            _IC_WEIGHTS_TECH if sector_class == "tech"
            else _IC_WEIGHTS_NON_TECH
        )

        # ── De-duplicate redundant signals ────────────────────────────────
        active_ids = {s.signal_id for s in fired}
        suppressed: set[str] = set()

        for cluster in _REDUNDANCY_CLUSTERS:
            cluster_active = cluster & active_ids
            if len(cluster_active) > 1:
                best = max(
                    cluster_active,
                    key=lambda sid: abs(ic_weights.get(sid, 0)),
                )
                suppressed |= cluster_active - {best}

        # ── Compute IC-weighted score ─────────────────────────────────────
        raw_score = 0.0
        max_possible = 0.0
        category_contributions: dict[str, float] = {}

        for sig in profile.signals:
            ic_w = ic_weights.get(sig.signal_id, _DEFAULT_IC_WEIGHT)

            if ic_w > 0:
                max_possible += ic_w

            if sig.signal_id in suppressed:
                continue

            if sig.fired and ic_w != 0:
                contribution = ic_w * sig.confidence
                raw_score += contribution
                cat_key = sig.category.value
                category_contributions[cat_key] = (
                    category_contributions.get(cat_key, 0.0) + contribution
                )

        # ── Normalize ─────────────────────────────────────────────────────
        if max_possible > 0:
            normalized = max(0.0, min(1.0, raw_score / max_possible))
        else:
            normalized = 0.0

        # ── Signal Level (2-tier buy system) ──────────────────────────────
        if normalized > STRONG_BUY_THRESHOLD:
            signal_level = SignalLevel.STRONG_BUY
        elif normalized > BUY_THRESHOLD:
            signal_level = SignalLevel.BUY
        else:
            signal_level = SignalLevel.HOLD

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

        return CompositeScore(
            overall_strength=round(normalized, 3),
            overall_confidence=confidence,
            signal_level=signal_level,
            category_scores=cat_scores,
            multi_category_bonus=False,
            dominant_category=dominant_category,
            active_categories=active_count,
        )
