"""
src/engines/alpha_signals/combiner.py
──────────────────────────────────────────────────────────────────────────────
Evidence-Based Signal Combiner V4 (Mar 2026).

Hybrid approach:
  - POSITIVE IC weights: Sharpe-normalized from per-signal backtest data
  - NEGATIVE IC weights: Restored from V3 Phase 0 IC screen (sector-validated)
  - ELIMINATED signals: Proven negative edge in per-signal backtest → IC = 0.0

Key insight from backtest comparison:
  V3 system's selectivity (75 trades / 4.9% of evals) came from negative IC
  signals SUBTRACTING from composite score. Removing them inflated trades to
  698 (45.9%) and destroyed alpha. The negative ICs are validated penalty
  filters, not noise.

Architecture:
  - Positive signals: weight = Sharpe@20d / max_sharpe (normalized 0-1)
  - Negative signals: restored from Phase 0 IC screen (sector-validated)
  - Eliminated: 7 signals with backtest-proven negative excess return
  - Buy thresholds: STRONG_BUY > 0.35, BUY > 0.20

2-Level Buy System + Position Sizing:
  - STRONG_BUY: composite_score > 0.35  →  100% position
  - BUY:        composite_score > 0.20  →   50% position
  - HOLD:       composite_score ≤ 0.20  →    0% position
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


# ══════════════════════════════════════════════════════════════════════════════
# IC WEIGHT TABLES — EVIDENCE-BASED V5 (Sharadar-validated)
# ══════════════════════════════════════════════════════════════════════════════
#
# Sources of evidence:
#   1. Per-signal backtest (20 signals, 10 tickers, 2Y) → Sharpe@20d
#   2. Phase 0 IC screen (sector-specific) → IC@20d per signal
#   3. ★ Sharadar diagnostic (20 stocks, 3Y, 2820 evals) → alpha vs baseline
#
# V5 changes (Sharadar-validated):
#   - Boosted: risk.pe_expensive, risk.ev_ebitda_expensive (contrarian alpha)
#   - Activated: flow.mfi_oversold, pricecycle.oversold_z (mean-reversion)
#   - Zeroed: value.fcf_yield_high, value.ebit_ev_high, value.div_yield_vs_hist
#             volatility.bb_compression, flow.dark_pool_absorption, vol.realized_vol
#
# Legend:
#   📊 = validated via per-signal backtest (strong evidence)
#   📈 = validated via Phase 0 IC screen (moderate evidence)
#   ★  = validated via Sharadar 20-stock diagnostic (2826 evals)
#   🔴 = eliminated (negative alpha on Sharadar universe)
#   ⚫ = unvalidated (IC = 0.0)

_IC_WEIGHTS_TECH: dict[str, float] = {
    # ── 📊 CORE ALPHA ─────────────────────────────────────────────────
    "quality.high_roic":               1.00,   # 📊 Sharpe=2.54, HR=72%
    "value.ev_ebitda_low":             0.89,   # 📊 Sharpe=2.25, HR=81%
    "value.pe_low":                    0.88,   # 📊 Sharpe=2.24, HR=73%
    "quality.low_leverage":            0.79,   # 📊 ★ Sharadar alpha=+1.15%
    "quality.high_roe":                0.79,   # 📊 Sharpe=2.01, HR=68%
    "risk.high_leverage":              0.74,   # 📊 Sharpe=1.88, HR=83% (contrarian)
    "value.shareholder_yield":         0.71,   # 📊 Sharpe=1.81, HR=71%
    "quality.asset_turnover_improving": 0.69,  # 📊 Sharpe=1.76, HR=71%

    # ── ★ SHARADAR-BOOSTED (contrarian/mean-reversion alpha) ──────────
    "risk.pe_expensive":               0.40,   # ★ alpha=+1.36% (was 0.0)
    "risk.ev_ebitda_expensive":        0.35,   # ★ alpha=+1.20% (was -0.02)
    "pricecycle.deep_pullback":        0.30,   # ★ alpha=+1.23% (was 0.18)
    "pricecycle.oversold_z":           0.28,   # ★ alpha=+1.11% (was 0.08)
    "flow.mfi_oversold":               0.25,   # ★ alpha=+1.21% (was 0.0)
    "value.pb_low":                    0.22,   # ★ alpha=+0.97% (was 0.0)

    # ── 📊 MODERATE ALPHA ─────────────────────────────────────────────
    "risk.macd_bearish":               0.12,   # 📊 Sharpe=0.61 (contrarian)
    "risk.death_cross":                0.26,   # 📈 IC=+0.26 (contrarian alpha)
    "quality.piotroski_f_score":       0.08,   # 📈 IC=+0.08
    "momentum.volume_surge":           0.05,   # 📈 IC=+0.05
    "flow.volume_price_divergence":    0.05,   # 📈 IC=+0.05
    "momentum.rsi_bullish":            0.03,   # 📈 IC=+0.03
    "value.ev_revenue_low":            0.20,   # ★ alpha=+0.64% (was 0.29)

    # ── 📈 PENALTY FILTERS (validated negative IC) ────────────────────
    "momentum.golden_cross":          -0.23,   # 📈 IC=-0.23
    "growth.operating_leverage":      -0.18,   # 📈 IC=-0.18
    "event.revenue_acceleration":     -0.16,   # 📈 IC=-0.16
    "value.peg_low":                  -0.15,   # 📈 IC=-0.15
    "event.earnings_surprise":        -0.15,   # 📈 IC=-0.15
    "momentum.price_above_ema20":     -0.14,   # 📈 IC=-0.14
    "momentum.adx_trend_strength":    -0.13,   # 📈 IC=-0.13
    "risk.revenue_decline":           -0.12,   # 📈 IC=-0.12
    "risk.earnings_decline":          -0.12,   # 📈 IC=-0.12
    "quality.stable_margins":         -0.12,   # 📈 IC=-0.12
    "quality.interest_coverage_fortress": -0.08, # 📈 IC=-0.08
    "growth.capex_intensity":         -0.06,   # 📈 IC=-0.06
    "fundmom.margin_expanding":       -0.05,   # 📈 IC=-0.05
    "pricecycle.near_52w_high_risk":  -0.05,   # 📈 IC=-0.05
    "growth.rule_of_40":              -0.04,   # 📈 IC=-0.04

    # ── 🔴 ELIMINATED (Sharadar-proven negative alpha) ────────────────
    "value.ebit_ev_high":              0.0,    # 🔴 ★ alpha=-1.11% (was 0.80)
    "value.div_yield_vs_hist":         0.0,    # 🔴 ★ alpha=-0.89% (was 0.30)
    "value.fcf_yield_high":            0.0,    # 🔴 ★ alpha=-0.76% (was 0.27)
    "volatility.realized_vol_regime":  0.0,    # 🔴 ★ alpha=-1.14% (was -0.06)
    "flow.dark_pool_absorption":       0.0,    # 🔴 ★ alpha=-0.52% (was -0.02)
    "momentum.macd_bullish":           0.0,    # 🔴 Sharpe=-0.20

    # ── Neutral / near-zero ───────────────────────────────────────────
    "event.high_beta_sector":          0.0,
    "risk.high_beta":                  0.0,
    "flow.unusual_volume":             0.0,
    "risk.negative_margin":            0.0,

    # ── ⚫ Unvalidated ────────────────────────────────────────────────
    "flow.short_interest_high":        0.0,
    "event.insider_buying":            0.0,
    "quality.accruals_quality":        0.0,
    "risk.high_accruals":              0.0,
    "flow.put_call_extreme":           0.0,
    "macro.credit_spread_tightening":  0.0,
    "macro.credit_spread_widening":    0.0,
    "growth.analyst_upgrade":          0.0,
}

_IC_WEIGHTS_NON_TECH: dict[str, float] = {
    # ── Non-tech IC weights (Phase 0 sector-specific validation) ────────
    # For signals that FLIP between sectors, use the Phase 0 non-tech IC.
    # For signals with no sector-specific data, use the per-signal backtest.

    # ── Positive (sorted by IC) ────────────────────────────────────────
    "growth.operating_leverage":       0.19,   # 📈 IC=+0.19 (FLIPPED from tech!)
    "risk.high_leverage":              0.12,   # 📈 IC=+0.12 (non-tech alpha)
    "risk.death_cross":                0.10,   # 📈 IC=+0.10
    "risk.macd_bearish":               0.10,   # 📈 IC=+0.10
    "risk.revenue_decline":            0.09,   # 📈 IC=+0.09 (FLIPPED from tech!)
    "growth.capex_intensity":          0.09,   # 📈 IC=+0.09 (FLIPPED from tech!)
    "fundmom.margin_expanding":        0.08,   # 📈 IC=+0.08 (FLIPPED from tech!)
    "value.shareholder_yield":         0.08,   # 📈 IC=+0.08
    "event.earnings_surprise":         0.08,   # 📈 IC=+0.08 (FLIPPED from tech!)
    "value.div_yield_vs_hist":         0.08,   # 📈 IC=+0.08
    "quality.interest_coverage_fortress": 0.08, # 📈 IC=+0.08 (FLIPPED from tech!)
    "risk.negative_margin":            0.07,   # 📈 IC=+0.07
    "momentum.adx_trend_strength":     0.06,   # 📈 IC=+0.06 (FLIPPED from tech!)
    "risk.earnings_decline":           0.05,   # 📈 IC=+0.05 (FLIPPED from tech!)
    "quality.high_roe":                0.04,   # 📈 IC=+0.04
    "value.pb_low":                    0.04,   # 📈 non-tech only
    "pricecycle.deep_pullback":        0.04,   # 📈 IC=+0.04
    "quality.low_leverage":            0.03,   # 📈 IC=+0.03
    "flow.volume_price_divergence":    0.02,   # 📈 IC=+0.02
    "quality.piotroski_f_score":       0.01,   # 📈 IC=+0.01

    # ── Per-signal backtest (no conflict with Phase 0) ─────────────────
    "quality.asset_turnover_improving": 0.69,  # 📊 Sharpe=1.76

    # ── Negative (penalty filters validated in non-tech) ───────────────
    "growth.rule_of_40":              -0.10,   # 📈 IC=-0.10
    "momentum.macd_bullish":          -0.10,   # 📈 IC=-0.10
    "risk.pe_expensive":              -0.08,   # 📈 IC=-0.08
    "risk.rsi_overbought":            -0.07,   # 📈 IC=-0.07
    "volatility.realized_vol_regime": -0.06,   # 📈 IC=-0.06
    "value.fcf_yield_high":           -0.06,   # 📈 IC=-0.06 (penalty in non-tech!)
    "quality.high_roic":              -0.05,   # 📈 IC=-0.05 (penalty in non-tech!)
    "momentum.price_above_ema20":     -0.05,   # 📈 IC=-0.05
    "pricecycle.near_52w_high_risk":  -0.05,   # 📈 IC=-0.05
    "pricecycle.stretched_above_mean": -0.04,  # 📈 IC=-0.04
    "flow.dark_pool_absorption":      -0.04,   # 📈 IC=-0.04
    "quality.stable_margins":         -0.02,   # 📈 IC=-0.02
    "event.revenue_acceleration":     -0.02,   # 📈 IC=-0.02
    "value.ev_revenue_low":           -0.02,   # 📈 IC=-0.02 (penalty in non-tech!)
    "risk.ev_ebitda_expensive":       -0.02,   # 📈 IC=-0.02
    "value.ebit_ev_high":             -0.01,   # 📈 IC=-0.01 (penalty in non-tech!)

    # ── Near-zero / neutral ────────────────────────────────────────────
    "momentum.rsi_bullish":            0.0,
    "momentum.volume_surge":           0.0,
    "event.high_beta_sector":          0.0,
    "risk.high_beta":                  0.0,
    "value.ev_ebitda_low":             0.0,    # 📈 IC≈0 in non-tech
    "value.pe_low":                    0.0,    # 📈 IC≈0 in non-tech
    "value.peg_low":                   0.0,
    "momentum.golden_cross":           0.0,    # 📈 IC≈0 in non-tech
    "flow.unusual_volume":             0.0,
    "pricecycle.oversold_z":           0.0,
    "flow.mfi_oversold":               0.0,

    # ── ⚫ New signals: unvalidated ────────────────────────────────────
    "flow.short_interest_high":        0.0,
    "event.insider_buying":            0.0,
    "quality.accruals_quality":        0.0,
    "risk.high_accruals":              0.0,
    "flow.put_call_extreme":           0.0,
    "macro.credit_spread_tightening":  0.0,
    "macro.credit_spread_widening":    0.0,
    "growth.analyst_upgrade":          0.0,
}

# Redundancy clusters (unchanged — empirically validated)
_REDUNDANCY_CLUSTERS: list[set[str]] = [
    {"value.pe_low", "value.ebit_ev_high"},
    {"value.ev_ebitda_low", "value.div_yield_vs_hist"},
    {"quality.high_roic", "quality.high_roe"},
    {"momentum.volume_surge", "flow.unusual_volume", "flow.volume_price_divergence"},
    {"risk.revenue_decline", "risk.earnings_decline"},
    {"value.peg_low", "event.earnings_surprise"},
    {"quality.accruals_quality", "risk.high_accruals"},
    {"macro.credit_spread_tightening", "macro.credit_spread_widening"},
    {"event.high_beta_sector", "risk.high_beta"},
    {"quality.interest_coverage_fortress", "growth.capex_intensity"},
    {"risk.pe_expensive", "risk.ev_ebitda_expensive"},
]

_DEFAULT_IC_WEIGHT = 0.0

# ── 2-Level Buy Thresholds ───────────────────────────────────────────────────
STRONG_BUY_THRESHOLD = 0.50
BUY_THRESHOLD = 0.35

# ── Position Sizing ─────────────────────────────────────────────────────────
_POSITION_SIZE = {
    SignalLevel.STRONG_BUY: 1.0,   # 100% of allocated capital
    SignalLevel.BUY:        0.5,   # 50% of allocated capital
    SignalLevel.HOLD:       0.0,   # no trade
}

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
    V4: Evidence-Based IC-weighted signal combiner.

    Hybrid approach:
      - Positive ICs from per-signal backtest (Sharpe-normalized)
      - Negative ICs from Phase 0 IC screen (sector-validated penalties)
      - Position sizing integrated into CompositeScore

    2-Level Buy System:
      - STRONG_BUY: composite_score > 0.35  →  position_size = 100%
      - BUY:        composite_score > 0.20  →  position_size =  50%
      - HOLD:       composite_score ≤ 0.20  →  position_size =   0%
    """

    def combine(
        self,
        profile: SignalProfile,
        sector: str = "",
    ) -> CompositeScore:
        """
        Compute evidence-based IC-weighted composite score.

        Args:
            profile: Evaluated signal profile for an asset.
            sector: Sector string for IC table selection.
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
                position_size_pct=0.0,
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

        # ── Position sizing ───────────────────────────────────────────────
        position_size = _POSITION_SIZE.get(signal_level, 0.0)

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
            position_size_pct=round(position_size, 2),
        )
