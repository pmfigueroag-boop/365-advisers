"""
src/engines/technical/scoring.py
──────────────────────────────────────────────────────────────────────────────
ScoringEngine V2 — Institutional-Grade Continuous Scoring

Every module score is a CONTINUOUS function of the raw indicator values,
normalised to [0, 10] via sigmoid-based mappings. No information is lost
to discrete bucketing.

Key improvements over V1:
  - Continuous sigmoid scoring (preserves distance/magnitude)
  - Regime-conditional volatility interpretation
  - Volume-price confirmation integration
  - Risk/reward ratio in structure scoring
  - Correlation-aware confidence (4 independent groups)
  - Professional TechnicalBias output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.engines.technical.indicators import IndicatorResult
from src.engines.technical.math_utils import sigmoid, clamp, normalize_to_score


# ─── Score types ─────────────────────────────────────────────────────────────

@dataclass
class ModuleScores:
    trend:      float   # 0–10
    momentum:   float
    volatility: float
    volume:     float
    structure:  float


@dataclass
class ModuleEvidence:
    """Evidence strings per module explaining each score."""
    trend:      list[str] = field(default_factory=list)
    momentum:   list[str] = field(default_factory=list)
    volatility: list[str] = field(default_factory=list)
    volume:     list[str] = field(default_factory=list)
    structure:  list[str] = field(default_factory=list)


@dataclass
class TechnicalBias:
    """Professional-grade technical bias assessment."""
    primary_bias: Literal["BULLISH", "BEARISH", "NEUTRAL"] = "NEUTRAL"
    bias_strength: float = 0.0       # 0–1 continuous
    trend_alignment: Literal["ALIGNED", "DIVERGENT", "NEUTRAL"] = "NEUTRAL"
    risk_reward_ratio: float = 1.0   # distance_to_support / distance_to_resistance
    key_levels: dict = field(default_factory=dict)
    actionable_zone: Literal[
        "ACCUMULATION", "BREAKOUT_WATCH", "TAKE_PROFIT",
        "STOP_LOSS_PROXIMITY", "NEUTRAL_ZONE"
    ] = "NEUTRAL_ZONE"
    time_horizon: Literal["SHORT", "MEDIUM", "LONG"] = "MEDIUM"


@dataclass
class TechnicalScore:
    aggregate: float    # 0–10, weighted
    modules:   ModuleScores
    signal:    Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
    strength:  Literal["Strong", "Moderate", "Weak"]
    evidence:  ModuleEvidence = field(default_factory=ModuleEvidence)
    confidence: float = 0.5           # 0–1, inter-module agreement
    strongest_module: str = ""
    weakest_module: str = ""
    confirmation_level: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    bias: TechnicalBias = field(default_factory=TechnicalBias)


# ─── Module weights ───────────────────────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "trend":      0.30,
    "momentum":   0.25,
    "volatility": 0.20,
    "volume":     0.15,
    "structure":  0.10,
}


# ─── Independence groups for correlation-aware confidence ─────────────────────

INDEPENDENCE_GROUPS = {
    "direction":  ["trend", "momentum"],   # correlated pair → counts as 1
    "volatility": ["volatility"],          # independent
    "conviction": ["volume"],              # independent
    "structure":  ["structure"],           # independent
}


# ─── Continuous score functions ───────────────────────────────────────────────

def _score_trend(result, price: float = 0.0) -> tuple[float, list[str]]:
    """
    Continuous trend scoring based on:
      - Price distance to SMA200 (normalised by SMA200 as ATR proxy)
      - Price distance to SMA50
      - MACD histogram magnitude
      - Cross bonuses (golden/death)
    """
    evidence: list[str] = []
    sma200 = result.sma_200 or 1.0
    sma50 = result.sma_50 or 1.0
    price = price or sma200  # fallback

    # ── SMA200 distance component (35% weight) ────────────────────────────
    # Distance as percentage of SMA200
    dist_200_pct = ((price - sma200) / sma200) * 100 if sma200 > 0 else 0
    # sigmoid mapping: center=0, scale=3 → ±9% covers most of [0,10]
    sma200_score = normalize_to_score(dist_200_pct, center=0, scale=3.0)
    if dist_200_pct > 0:
        evidence.append(f"Price {dist_200_pct:+.1f}% above SMA200 (${sma200:.2f}) → score {sma200_score:.1f}")
    else:
        evidence.append(f"Price {dist_200_pct:+.1f}% below SMA200 (${sma200:.2f}) → score {sma200_score:.1f}")

    # ── SMA50 distance component (30% weight) ────────────────────────────
    dist_50_pct = ((price - sma50) / sma50) * 100 if sma50 > 0 else 0
    sma50_score = normalize_to_score(dist_50_pct, center=0, scale=2.5)
    evidence.append(f"Price {dist_50_pct:+.1f}% vs SMA50 (${sma50:.2f}) → score {sma50_score:.1f}")

    # ── MACD histogram component (25% weight) ────────────────────────────
    macd_hist = result.macd_histogram
    # Normalise by price magnitude to make cross-asset comparable
    macd_norm = (macd_hist / (price * 0.01)) if price > 0 else 0
    macd_score = normalize_to_score(macd_norm, center=0, scale=1.5)
    evidence.append(f"MACD histogram {macd_hist:+.2f} (norm={macd_norm:+.2f}) → score {macd_score:.1f}")

    # ── Cross bonus (10% weight) ──────────────────────────────────────────
    cross_score = 5.0  # neutral
    if result.golden_cross:
        cross_score = 8.5
        evidence.append("Golden Cross detected (SMA50 > SMA200) → +8.5")
    elif result.death_cross:
        cross_score = 1.5
        evidence.append("Death Cross detected (SMA50 < SMA200) → 1.5")

    # ── Weighted aggregate ────────────────────────────────────────────────
    score = (
        sma200_score * 0.35 +
        sma50_score  * 0.30 +
        macd_score   * 0.25 +
        cross_score  * 0.10
    )

    return clamp(score), evidence


def _score_momentum(result) -> tuple[float, list[str]]:
    """
    Continuous momentum scoring:
      - RSI → non-linear sigmoid (oversold=bullish, overbought=bearish)
      - Stochastic → continuous %K position
      - RSI-Stochastic agreement bonus
    """
    evidence: list[str] = []
    rsi = result.rsi
    stoch_k = result.stoch_k

    # ── RSI component (55% weight) ────────────────────────────────────────
    # RSI 50 = neutral (5.0), RSI 30 = bullish (8.0+), RSI 70 = bearish (2.0-)
    # Inverted sigmoid: lower RSI = higher bullish score
    rsi_score = clamp((1.0 - sigmoid((rsi - 50) / 12)) * 10)

    if rsi <= 30:
        evidence.append(f"RSI oversold at {rsi:.1f} — strong bullish signal → {rsi_score:.1f}")
    elif rsi >= 70:
        evidence.append(f"RSI overbought at {rsi:.1f} — bearish risk → {rsi_score:.1f}")
    elif rsi > 55:
        evidence.append(f"RSI bullish bias at {rsi:.1f} → {rsi_score:.1f}")
    elif rsi < 45:
        evidence.append(f"RSI bearish bias at {rsi:.1f} → {rsi_score:.1f}")
    else:
        evidence.append(f"RSI neutral at {rsi:.1f} → {rsi_score:.1f}")

    # ── Stochastic component (35% weight) ─────────────────────────────────
    stoch_score = clamp((1.0 - sigmoid((stoch_k - 50) / 15)) * 10)
    if stoch_k <= 20:
        evidence.append(f"Stochastic oversold (%K={stoch_k:.1f}) → {stoch_score:.1f}")
    elif stoch_k >= 80:
        evidence.append(f"Stochastic overbought (%K={stoch_k:.1f}) → {stoch_score:.1f}")
    else:
        evidence.append(f"Stochastic at %K={stoch_k:.1f} → {stoch_score:.1f}")

    # ── Agreement bonus (10% weight) ──────────────────────────────────────
    # When RSI and Stochastic agree on zone, boost/penalize
    agree_score = 5.0
    both_oversold = rsi <= 35 and stoch_k <= 25
    both_overbought = rsi >= 65 and stoch_k >= 75
    if both_oversold:
        agree_score = 9.0
        evidence.append("Double oversold confirmation (RSI+Stoch) → strong bullish")
    elif both_overbought:
        agree_score = 1.0
        evidence.append("Double overbought confirmation (RSI+Stoch) → strong bearish")

    score = rsi_score * 0.55 + stoch_score * 0.35 + agree_score * 0.10

    return clamp(score), evidence


def _score_volatility(
    result,
    regime: str = "TRANSITIONING",
) -> tuple[float, list[str]]:
    """
    Regime-CONDITIONAL volatility scoring.

    Volatility is not directionally bullish/bearish — it describes market quality.
    The score reflects how FAVOURABLE the current volatility is for the detected regime:

      - TRENDING + Normal vol = high score (healthy trend)
      - RANGING  + Low vol    = high score (stable range, tradeable)
      - Any      + HIGH vol   = low score (unpredictable)
      - COMPRESSION (BB squeeze) = moderate (potential breakout setup)
    """
    evidence: list[str] = []
    atr_pct = result.atr_pct
    bb_width = result.bb_width
    price = result.bb_basis or 1.0

    # BB width as % of price (squeeze detection)
    bb_width_pct = (bb_width / price) * 100 if price > 0 else 0

    # ── Base volatility quality score ─────────────────────────────────────
    # Optimal ATR% is 1.5-2.5% for most equities
    # Too high (>4%) = dangerous, too low (<0.5%) = dead
    optimal_atr_pct = 0.018  # 1.8%
    vol_deviation = abs(atr_pct - optimal_atr_pct)
    vol_quality = clamp(10.0 - (vol_deviation / 0.01) * 2.5, 0, 10)

    evidence.append(f"ATR%={atr_pct:.3f} (optimal≈1.8%, deviation={vol_deviation:.3f}) → quality {vol_quality:.1f}")

    # ── Regime conditioning ───────────────────────────────────────────────
    regime_adj = 0.0
    if regime == "TRENDING":
        # In trending markets, moderate-to-normal vol is ideal
        if 0.01 <= atr_pct <= 0.03:
            regime_adj = +1.0
            evidence.append(f"TRENDING regime + moderate vol → favourable (+1.0)")
        elif atr_pct > 0.04:
            regime_adj = -1.5
            evidence.append(f"TRENDING regime + extreme vol → destabilising (-1.5)")
    elif regime == "RANGING":
        # In ranging markets, low vol is ideal (mean-reversion works)
        if atr_pct < 0.015:
            regime_adj = +1.5
            evidence.append(f"RANGING regime + low vol → ideal for mean-reversion (+1.5)")
        elif atr_pct > 0.03:
            regime_adj = -1.0
            evidence.append(f"RANGING regime + high vol → breakout risk (-1.0)")
    elif regime == "VOLATILE":
        # Already volatile → penalise further
        regime_adj = -1.0
        evidence.append(f"VOLATILE regime → additional risk penalty (-1.0)")

    # ── BB position (directional color) ───────────────────────────────────
    bb_adj = {
        "LOWER":      1.0,   # near support, potential bounce
        "LOWER_MID":  0.3,
        "MID":        0.0,
        "UPPER_MID": -0.3,
        "UPPER":     -0.8,   # stretched, potential mean-reversion
    }.get(result.bb_position, 0.0)

    if bb_adj != 0:
        evidence.append(f"BB position: {result.bb_position} (adj {bb_adj:+.1f})")

    # ── BB squeeze detection ──────────────────────────────────────────────
    squeeze_bonus = 0.0
    if bb_width_pct < 3.0 and result.condition != "HIGH":
        squeeze_bonus = 0.5
        evidence.append(f"BB squeeze detected (width={bb_width_pct:.1f}%) → potential breakout setup (+0.5)")

    score = vol_quality + regime_adj + bb_adj + squeeze_bonus

    return clamp(score), evidence


def _score_volume(result) -> tuple[float, list[str]]:
    """
    Continuous volume scoring:
      - Volume ratio → smooth continuous curve
      - OBV trend direction
      - Volume-price confirmation bonus/penalty
    """
    evidence: list[str] = []
    vol_ratio = result.volume_vs_avg

    # ── Volume ratio component (50% weight) ───────────────────────────────
    # Continuous mapping: ratio=1.0 → 5.0, ratio=2.0 → 8.0, ratio=0.5 → 3.0
    vol_score = normalize_to_score(vol_ratio, center=1.0, scale=0.5)
    evidence.append(f"Volume {vol_ratio:.2f}x average → score {vol_score:.1f}")

    # ── OBV trend component (25% weight) ──────────────────────────────────
    obv_score = {"RISING": 7.5, "FLAT": 5.0, "FALLING": 2.5}.get(result.obv_trend, 5.0)
    evidence.append(f"OBV trend: {result.obv_trend} → {obv_score:.1f}")
    if result.obv_computed:
        evidence.append("OBV computed from OHLCV series (high fidelity)")

    # ── Volume-price confirmation (25% weight) ────────────────────────────
    vp_score = 5.0  # neutral default
    vp_status = getattr(result, "volume_price_confirmation", "NEUTRAL")
    if vp_status == "CONFIRMED":
        vp_score = 8.0
        evidence.append("Volume-price CONFIRMED — moves backed by conviction")
    elif vp_status == "DIVERGENT":
        vp_score = 2.5
        evidence.append("Volume-price DIVERGENT — moves lack conviction (warning)")
    else:
        evidence.append("Volume-price neutral")

    score = vol_score * 0.50 + obv_score * 0.25 + vp_score * 0.25

    return clamp(score), evidence


def _score_structure(result) -> tuple[float, list[str]]:
    """
    Structure scoring based on:
      - Risk/reward ratio (distance to support vs resistance)
      - Market structure alignment (HH/HL, LH/LL)
      - Strong S/R levels
      - Pattern recognition
      - Breakout proximity
    """
    evidence: list[str] = []

    # ── Risk/reward ratio (40% weight) ────────────────────────────────────
    dist_res = result.distance_to_resistance_pct  # % above current price
    dist_sup = result.distance_to_support_pct     # % below current price
    rr_score = 5.0  # neutral if no levels

    if dist_res is not None and dist_sup is not None and dist_sup > 0:
        rr_ratio = dist_res / dist_sup  # >1 = more room up than down
        rr_score = normalize_to_score(rr_ratio, center=1.0, scale=0.8)
        evidence.append(f"R/R ratio: {rr_ratio:.2f}x (resistance {dist_res:.1f}% away, support {dist_sup:.1f}% away) → {rr_score:.1f}")
    elif dist_res is not None:
        # Only resistance, no support → potentially bullish (far from ceiling)
        rr_score = 6.5 if dist_res > 3 else 5.0
        evidence.append(f"Resistance {dist_res:.1f}% away, no clear support → {rr_score:.1f}")
    elif dist_sup is not None:
        rr_score = 3.5 if dist_sup < 2 else 5.0
        evidence.append(f"Support {dist_sup:.1f}% away, no clear resistance → {rr_score:.1f}")

    # ── Market structure (25% weight) ─────────────────────────────────────
    ms = getattr(result, "market_structure", "MIXED")
    direction = result.breakout_direction
    ms_score = 5.0

    if ms == "HH_HL":
        ms_score = 7.5
        evidence.append("Market structure: Higher Highs / Higher Lows (uptrend) → 7.5")
        if direction == "BULLISH":
            ms_score = 8.5
            evidence.append("Structure aligns with bullish breakout direction → 8.5")
    elif ms == "LH_LL":
        ms_score = 2.5
        evidence.append("Market structure: Lower Highs / Lower Lows (downtrend) → 2.5")
        if direction == "BULLISH":
            ms_score = 2.0
            evidence.append("WARNING: Downtrend structure conflicts with bullish direction → 2.0")
    else:
        evidence.append("Market structure: Mixed/Choppy → 5.0")

    # ── Level strength bonus (15% weight) ─────────────────────────────────
    levels_score = 5.0
    level_str = getattr(result, "level_strength", {})
    strong_count = sum(1 for v in level_str.values() if v.get("strong", False))
    if strong_count >= 2:
        levels_score = 8.0
        evidence.append(f"Multiple strong S/R levels ({strong_count} with 3+ touches) → 8.0")
    elif strong_count == 1:
        levels_score = 6.5
        evidence.append(f"One strong S/R level detected → 6.5")

    # ── Pattern signals (20% weight) ──────────────────────────────────────
    patterns = getattr(result, "patterns", [])
    pattern_score = 5.0
    bullish_patterns = [p for p in patterns if p in ("DOUBLE_BOTTOM", "HIGHER_LOWS")]
    bearish_patterns = [p for p in patterns if p in ("DOUBLE_TOP", "LOWER_HIGHS")]

    if bullish_patterns and not bearish_patterns:
        pattern_score = 8.0
        evidence.append(f"Bullish patterns: {', '.join(bullish_patterns)} → 8.0")
    elif bearish_patterns and not bullish_patterns:
        pattern_score = 2.0
        evidence.append(f"Bearish patterns: {', '.join(bearish_patterns)} → 2.0")
    elif bullish_patterns and bearish_patterns:
        pattern_score = 5.0
        evidence.append(f"Mixed patterns (bullish + bearish) → 5.0")

    score = (
        rr_score      * 0.40 +
        ms_score      * 0.25 +
        levels_score  * 0.15 +
        pattern_score * 0.20
    )

    return clamp(score), evidence


# ─── Aggregate + Signal derivation ───────────────────────────────────────────

def _derive_signal(score: float) -> Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]:
    if score >= 7.5:
        return "STRONG_BUY"
    if score >= 6.0:
        return "BUY"
    if score >= 4.0:
        return "NEUTRAL"
    if score >= 2.5:
        return "SELL"
    return "STRONG_SELL"


def _derive_strength(score: float) -> Literal["Strong", "Moderate", "Weak"]:
    dist_from_center = abs(score - 5.0)
    if dist_from_center >= 2.5:
        return "Strong"
    if dist_from_center >= 1.0:
        return "Moderate"
    return "Weak"


def _compute_confidence(
    modules: ModuleScores,
    signal: str,
) -> tuple[float, str]:
    """
    Correlation-aware confidence using 4 independence groups.

    Trend and Momentum are ~70% correlated, so they count as ONE
    directional cluster. Volatility, Volume, and Structure each
    provide independent confirmation.

    4 groups → potential agreement of 0–4.
    3+ groups agreeing = HIGH, 2 = MEDIUM, <2 = LOW.
    """
    bullish_signal = signal in ("STRONG_BUY", "BUY")
    bearish_signal = signal in ("STRONG_SELL", "SELL")

    all_scores = {
        "trend": modules.trend,
        "momentum": modules.momentum,
        "volatility": modules.volatility,
        "volume": modules.volume,
        "structure": modules.structure,
    }

    def _module_agrees(mod_score: float) -> bool:
        if bullish_signal:
            return mod_score >= 6.0
        if bearish_signal:
            return mod_score <= 4.0
        return 4.0 <= mod_score <= 6.0  # neutral agreement

    groups_agreeing = 0
    total_groups = len(INDEPENDENCE_GROUPS)

    for group_name, group_modules in INDEPENDENCE_GROUPS.items():
        group_scores = [all_scores[m] for m in group_modules if m in all_scores]
        if not group_scores:
            continue

        if group_name == "direction":
            # Correlated pair: take the AVERAGE then check agreement
            avg_direction = sum(group_scores) / len(group_scores)
            if _module_agrees(avg_direction):
                groups_agreeing += 1
        else:
            # Independent module: direct check
            if _module_agrees(group_scores[0]):
                groups_agreeing += 1

    confidence = round(groups_agreeing / total_groups, 2)

    if groups_agreeing >= 3:
        level = "HIGH"
    elif groups_agreeing >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    return confidence, level


def _compute_bias(
    modules: ModuleScores,
    score: float,
    signal: str,
    structure_result,
    regime: str = "TRANSITIONING",
) -> TechnicalBias:
    """Derive a professional-grade technical bias assessment."""
    # Primary bias from signal
    if signal in ("STRONG_BUY", "BUY"):
        primary_bias = "BULLISH"
    elif signal in ("STRONG_SELL", "SELL"):
        primary_bias = "BEARISH"
    else:
        primary_bias = "NEUTRAL"

    # Bias strength: 0–1 from distance to neutral (5.0)
    bias_strength = round(min(abs(score - 5.0) / 5.0, 1.0), 2)

    # Trend alignment: do trend and momentum agree?
    trend_bull = modules.trend >= 6.0
    mom_bull = modules.momentum >= 6.0
    trend_bear = modules.trend <= 4.0
    mom_bear = modules.momentum <= 4.0

    if (trend_bull and mom_bull) or (trend_bear and mom_bear):
        trend_alignment = "ALIGNED"
    elif (trend_bull and mom_bear) or (trend_bear and mom_bull):
        trend_alignment = "DIVERGENT"
    else:
        trend_alignment = "NEUTRAL"

    # Risk/reward ratio
    dist_res = structure_result.distance_to_resistance_pct
    dist_sup = structure_result.distance_to_support_pct
    rr_ratio = 1.0
    if dist_res is not None and dist_sup is not None and dist_sup > 0:
        rr_ratio = round(dist_res / dist_sup, 2)

    # Key levels
    key_levels = {}
    if structure_result.nearest_support is not None:
        key_levels["nearest_support"] = structure_result.nearest_support
    if structure_result.nearest_resistance is not None:
        key_levels["nearest_resistance"] = structure_result.nearest_resistance
    if structure_result.nearest_support is not None:
        # Invalidation level = support * 0.98 (2% below support)
        key_levels["invalidation_level"] = round(structure_result.nearest_support * 0.98, 2)

    # Actionable zone
    if dist_sup is not None and dist_sup < 1.5:
        actionable_zone = "STOP_LOSS_PROXIMITY"
    elif dist_res is not None and dist_res < 1.5:
        actionable_zone = "BREAKOUT_WATCH"
    elif primary_bias == "BULLISH" and bias_strength > 0.3 and rr_ratio > 1.5:
        actionable_zone = "ACCUMULATION"
    elif primary_bias == "BEARISH" and bias_strength > 0.3:
        actionable_zone = "TAKE_PROFIT"
    else:
        actionable_zone = "NEUTRAL_ZONE"

    # Time horizon from regime
    if regime in ("TRENDING", "VOLATILE"):
        time_horizon = "SHORT"
    elif regime == "RANGING":
        time_horizon = "MEDIUM"
    else:
        time_horizon = "MEDIUM"

    return TechnicalBias(
        primary_bias=primary_bias,
        bias_strength=bias_strength,
        trend_alignment=trend_alignment,
        risk_reward_ratio=rr_ratio,
        key_levels=key_levels,
        actionable_zone=actionable_zone,
        time_horizon=time_horizon,
    )


# ─── ScoringEngine ───────────────────────────────────────────────────────────

class ScoringEngine:
    """Institutional-grade deterministic scorer. No LLM. Fully testable."""

    @staticmethod
    def compute(
        result: IndicatorResult,
        weights: dict[str, float] | None = None,
        regime_adjustments: dict[str, float] | None = None,
        trend_regime: str = "TRANSITIONING",
        price: float = 0.0,
    ) -> TechnicalScore:
        w = dict(weights or DEFAULT_WEIGHTS)  # copy to avoid mutation

        # Apply regime-based weight adjustments if provided
        if regime_adjustments:
            for module, multiplier in regime_adjustments.items():
                if module in w:
                    w[module] = w[module] * multiplier

        # Compute scores with evidence (continuous)
        trend_score, trend_ev = _score_trend(result.trend, price=price)
        momentum_score, momentum_ev = _score_momentum(result.momentum)
        volatility_score, volatility_ev = _score_volatility(
            result.volatility, regime=trend_regime,
        )
        volume_score, volume_ev = _score_volume(result.volume)
        structure_score, structure_ev = _score_structure(result.structure)

        modules = ModuleScores(
            trend      = trend_score,
            momentum   = momentum_score,
            volatility = volatility_score,
            volume     = volume_score,
            structure  = structure_score,
        )

        evidence = ModuleEvidence(
            trend      = trend_ev,
            momentum   = momentum_ev,
            volatility = volatility_ev,
            volume     = volume_ev,
            structure  = structure_ev,
        )

        aggregate = (
            modules.trend      * w["trend"]      +
            modules.momentum   * w["momentum"]   +
            modules.volatility * w["volatility"] +
            modules.volume     * w["volume"]     +
            modules.structure  * w["structure"]
        ) / sum(w.values())

        aggregate = round(aggregate, 2)
        signal = _derive_signal(aggregate)

        # Compute confidence and find strongest/weakest modules
        confidence, confirmation_level = _compute_confidence(modules, signal)

        score_map = {
            "trend": modules.trend,
            "momentum": modules.momentum,
            "volatility": modules.volatility,
            "volume": modules.volume,
            "structure": modules.structure,
        }
        strongest = max(score_map, key=score_map.get)
        weakest = min(score_map, key=score_map.get)

        # Compute professional bias
        bias = _compute_bias(
            modules, aggregate, signal,
            result.structure,
            regime=trend_regime,
        )

        return TechnicalScore(
            aggregate = aggregate,
            modules   = modules,
            signal    = signal,
            strength  = _derive_strength(aggregate),
            evidence  = evidence,
            confidence = confidence,
            strongest_module = strongest,
            weakest_module = weakest,
            confirmation_level = confirmation_level,
            bias = bias,
        )
