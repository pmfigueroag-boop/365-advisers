"""
src/engines/technical/war_room/conviction_ceiling.py
──────────────────────────────────────────────────────────────────────────────
Data-anchored conviction ceiling.

Prevents LLM hallucination in conviction values by computing the maximum
justifiable conviction from three pillars:
  1. Indicator value (the raw number)
  2. Statistical deviation (z-score vs asset/sector norms)
  3. Doctrinal zone (what theory says about the reading)

The LLM can lower conviction (qualitative judgement) but cannot raise it
beyond what the data supports.

  ceiling = 0.3 + 0.7 × max(doctrinal_zone_score, statistical_deviation)
  final_conviction = min(llm_conviction, ceiling)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("365advisers.engines.technical.war_room.conviction_ceiling")


# ─── Doctrinal Zone Tables ────────────────────────────────────────────────────
#
# Each domain has rules that map raw indicator values to a zone_score ∈ [0, 1].
#   1.0 = extreme / doctrinally significant → high conviction justified
#   0.5 = mid-zone / moderate signal
#   0.0 = neutral zone / no directional significance

def _momentum_zone(details: dict) -> float:
    """RSI and Stoch %K doctrinal zones (Wilder, Lane)."""
    scores: list[float] = []

    rsi = _float(details.get("rsi"))
    if rsi is not None:
        if rsi <= 25 or rsi >= 75:
            scores.append(1.0)       # extreme — strong mean-reversion signal
        elif rsi <= 30 or rsi >= 70:
            scores.append(0.8)       # classic oversold/overbought
        elif rsi <= 40 or rsi >= 60:
            scores.append(0.4)       # mild directional lean
        else:
            scores.append(0.0)       # 40-60 = dead zone

    stoch_k = _float(details.get("stoch_k"))
    if stoch_k is not None:
        if stoch_k <= 15 or stoch_k >= 85:
            scores.append(1.0)
        elif stoch_k <= 20 or stoch_k >= 80:
            scores.append(0.8)
        elif stoch_k <= 30 or stoch_k >= 70:
            scores.append(0.4)
        else:
            scores.append(0.0)

    # Divergence adds conviction
    div = details.get("divergence", "none")
    if div and str(div).lower() not in ("none", ""):
        div_str = _float(details.get("divergence_strength")) or 0.5
        scores.append(min(1.0, div_str))

    return max(scores) if scores else 0.3


def _trend_zone(details: dict) -> float:
    """Dow Theory + trend-following zones."""
    scores: list[float] = []

    # Price vs SMA200 — large deviations are significant
    pv200 = _float(details.get("price_vs_sma200"))
    if pv200 is not None:
        abs_pv = abs(pv200)
        if abs_pv >= 8.0:
            scores.append(1.0)       # >8% from SMA200 — extreme
        elif abs_pv >= 5.0:
            scores.append(0.7)
        elif abs_pv >= 3.0:
            scores.append(0.4)
        else:
            scores.append(0.1)       # very close to SMA200 — no trend signal

    # Golden/death cross — binary but cross_age matters
    gc = details.get("golden_cross", False)
    dc = details.get("death_cross", False)
    cross_age = _float(details.get("cross_age_bars")) or 999
    if gc or dc:
        if cross_age <= 5:
            scores.append(1.0)       # fresh cross — highest significance
        elif cross_age <= 20:
            scores.append(0.7)       # recent cross
        elif cross_age <= 60:
            scores.append(0.4)       # aging cross
        else:
            scores.append(0.2)       # old cross — significance fading

    # MACD histogram strength
    macd_h = _float(details.get("macd_histogram"))
    if macd_h is not None:
        abs_h = abs(macd_h)
        if abs_h >= 2.0:
            scores.append(0.8)
        elif abs_h >= 1.0:
            scores.append(0.5)
        elif abs_h >= 0.3:
            scores.append(0.3)
        else:
            scores.append(0.0)

    return max(scores) if scores else 0.2


def _volatility_zone(details: dict, asset_ctx: dict) -> float:
    """Natenberg / VIX framework zones."""
    scores: list[float] = []

    # BB position: extreme = near/beyond bands
    bb_pos = _float(details.get("bb_position"))
    if bb_pos is not None:
        if bb_pos <= 0.05 or bb_pos >= 0.95:
            scores.append(1.0)       # beyond Bollinger Bands
        elif bb_pos <= 0.15 or bb_pos >= 0.85:
            scores.append(0.7)
        elif bb_pos <= 0.25 or bb_pos >= 0.75:
            scores.append(0.4)
        else:
            scores.append(0.0)       # mid-band = no signal

    # ATR% vs asset's optimal — deviation from norm
    atr_pct = _float(details.get("atr_pct"))
    opt_atr = _float(asset_ctx.get("optimal_atr_pct"))
    if atr_pct is not None and opt_atr and opt_atr > 0:
        ratio = atr_pct / opt_atr
        if ratio >= 2.0 or ratio <= 0.4:
            scores.append(1.0)       # extreme vol expansion/compression
        elif ratio >= 1.5 or ratio <= 0.6:
            scores.append(0.7)
        elif ratio >= 1.2 or ratio <= 0.8:
            scores.append(0.3)
        else:
            scores.append(0.0)       # normal volatility

    # BB width vs median — context-calibrated
    bb_w = _float(details.get("bb_width"))
    bb_med = _float(asset_ctx.get("bb_width_median"))
    if bb_w is not None and bb_med and bb_med > 0:
        w_ratio = bb_w / bb_med
        if w_ratio >= 2.0 or w_ratio <= 0.4:
            scores.append(0.9)
        elif w_ratio >= 1.5 or w_ratio <= 0.6:
            scores.append(0.5)
        else:
            scores.append(0.1)

    return max(scores) if scores else 0.2


def _volume_zone(details: dict) -> float:
    """Wyckoff method zones."""
    scores: list[float] = []

    # Volume vs average — magnitude of activity
    vol_avg = _float(details.get("volume_vs_avg"))
    if vol_avg is not None:
        if vol_avg >= 2.5:
            scores.append(1.0)       # climactic volume
        elif vol_avg >= 2.0:
            scores.append(0.8)
        elif vol_avg >= 1.5:
            scores.append(0.5)
        elif vol_avg <= 0.5:
            scores.append(0.6)       # abnormally low — also significant (drying up)
        else:
            scores.append(0.1)       # normal volume

    # OBV trend — confirms/denies price direction
    obv = details.get("obv_trend", "")
    if obv:
        obv_str = str(obv).lower()
        if obv_str in ("strong_bullish", "strong_bearish"):
            scores.append(0.8)
        elif obv_str in ("bullish", "bearish"):
            scores.append(0.5)
        else:
            scores.append(0.1)

    # Volume-price confirmation
    vpc = details.get("volume_price_confirmation")
    if vpc is not None:
        if vpc is True or str(vpc).lower() == "true":
            scores.append(0.6)       # confirmation adds conviction
        else:
            scores.append(0.0)

    return max(scores) if scores else 0.2


def _structure_zone(details: dict) -> float:
    """Market Profile / Price Action zones."""
    scores: list[float] = []

    # Distance to support — closer = more significant
    dist_s = _float(details.get("distance_to_support_pct"))
    if dist_s is not None:
        if dist_s <= 0.5:
            scores.append(1.0)       # right at support
        elif dist_s <= 1.0:
            scores.append(0.8)
        elif dist_s <= 2.0:
            scores.append(0.5)
        elif dist_s <= 3.0:
            scores.append(0.3)
        else:
            scores.append(0.1)       # far from support

    # Distance to resistance
    dist_r = _float(details.get("distance_to_resistance_pct"))
    if dist_r is not None:
        if dist_r <= 0.5:
            scores.append(1.0)       # right at resistance
        elif dist_r <= 1.0:
            scores.append(0.8)
        elif dist_r <= 2.0:
            scores.append(0.5)
        elif dist_r <= 3.0:
            scores.append(0.3)
        else:
            scores.append(0.1)

    # Breakout probability
    bp = _float(details.get("breakout_probability"))
    if bp is not None:
        scores.append(min(1.0, bp))

    # Level strength
    ls = _float(details.get("level_strength"))
    if ls is not None:
        scores.append(min(1.0, ls))

    # Patterns
    patterns = details.get("patterns")
    if patterns and isinstance(patterns, list) and len(patterns) > 0:
        scores.append(0.7)           # identified pattern adds conviction

    return max(scores) if scores else 0.2


def _mtf_zone(details: dict) -> float:
    """Elder Triple Screen zones."""
    agreement = _float(details.get("agreement_count"))
    total = 6  # 6 timeframes

    if agreement is not None:
        ratio = agreement / total
        if ratio >= 5 / 6:      # ≥5 aligned
            return 1.0
        elif ratio >= 4 / 6:    # 4 aligned
            return 0.7
        elif ratio >= 3 / 6:    # 3 aligned
            return 0.4
        else:
            return 0.1          # <3 aligned — low conviction justified

    # Fallback: check agreement_level string
    level = str(details.get("agreement_level", "")).lower()
    if level in ("strong", "very_strong"):
        return 0.9
    elif level in ("moderate",):
        return 0.5
    elif level in ("weak", "none"):
        return 0.2

    return 0.3


# ─── Domain dispatcher ───────────────────────────────────────────────────────

_ZONE_FUNCTIONS = {
    "momentum": lambda d, a: _momentum_zone(d),
    "trend": lambda d, a: _trend_zone(d),
    "volatility": _volatility_zone,
    "volume": lambda d, a: _volume_zone(d),
    "structure": lambda d, a: _structure_zone(d),
    "mtf": lambda d, a: _mtf_zone(d),
}


def compute_ceiling(domain: str, details: dict, asset_ctx: dict | None = None) -> float:
    """
    Compute the maximum justifiable conviction for an agent.

    Parameters
    ----------
    domain : str
        Agent domain (trend, momentum, volatility, volume, structure, mtf).
    details : dict
        Raw indicator values for the agent's domain.
    asset_ctx : dict | None
        Asset-specific statistics (optimal_atr_pct, bb_width_median, etc.).

    Returns
    -------
    float
        Conviction ceiling ∈ [0.3, 1.0].
    """
    ctx = asset_ctx or {}
    zone_fn = _ZONE_FUNCTIONS.get(domain)
    if not zone_fn:
        logger.debug(f"No zone function for domain '{domain}', using default ceiling 0.7")
        return 0.7

    zone_score = zone_fn(details, ctx)
    ceiling = 0.3 + 0.7 * zone_score
    ceiling = min(1.0, round(ceiling, 2))

    logger.debug(f"Conviction ceiling [{domain}]: zone_score={zone_score:.2f} → ceiling={ceiling}")
    return ceiling


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _float(val: Any) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
