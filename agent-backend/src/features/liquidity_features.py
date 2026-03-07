"""
src/features/liquidity_features.py
──────────────────────────────────────────────────────────────────────────────
Extracts liquidity features from the EnhancedMarketData contract
(produced by the Polygon adapter or its fallback chain).

This bridges EDPL data → existing Liquidity Engine, Cost Model, and
Fill Model interfaces that expect plain dicts / floats.
"""

from __future__ import annotations

import logging
from typing import Any

from src.data.external.contracts.enhanced_market import (
    EnhancedMarketData,
    LiquiditySnapshot,
)

logger = logging.getLogger("365advisers.features.liquidity")


def extract_liquidity_market_data(
    enhanced: EnhancedMarketData,
    fallback_price: float = 0.0,
    fallback_market_cap: float = 0.0,
) -> dict[str, Any]:
    """
    Transform EnhancedMarketData into the dict format expected by
    ``LiquidityEstimator.estimate()``.

    Returns a dict with keys:
      - avg_volume_20d
      - avg_price
      - market_cap
      - bid_ask_spread

    If Polygon data is not available (empty contract), falls back to
    the provided fallback values, allowing the Liquidity Engine to
    continue with whatever data is available.
    """
    liquidity = enhanced.liquidity or LiquiditySnapshot.empty(enhanced.ticker)

    # ADV from liquidity snapshot or compute from bars
    adv = liquidity.avg_daily_volume_30d or 0.0
    if adv == 0 and enhanced.intraday_bars:
        # Compute from intraday bars
        vols = [b.volume for b in enhanced.intraday_bars if b.volume > 0]
        adv = sum(vols) / len(vols) if vols else 0.0

    # Average price from bars or fallback
    avg_price = fallback_price
    if enhanced.intraday_bars:
        prices = [b.close for b in enhanced.intraday_bars if b.close > 0]
        avg_price = sum(prices) / len(prices) if prices else fallback_price
    elif enhanced.last_trade_price:
        avg_price = enhanced.last_trade_price

    # Bid-ask spread in dollars (estimator expects dollars, not bps)
    spread_dollars = 0.01  # default 1 cent
    if liquidity.bid_ask_spread_bps is not None and avg_price > 0:
        spread_dollars = (liquidity.bid_ask_spread_bps / 10000) * avg_price

    return {
        "avg_volume_20d": adv,
        "avg_price": avg_price,
        "market_cap": fallback_market_cap,
        "bid_ask_spread": spread_dollars,
    }


def extract_intraday_volume_profile(
    enhanced: EnhancedMarketData,
    bins: int = 24,
) -> list[float] | None:
    """
    Extract a normalized intraday volume profile from Polygon intraday bars.

    Used by ``FillModel.compute_vwap_slippage()`` to replace the default
    U-shaped synthetic profile with real market data.

    Returns None if insufficient intraday data is available (the FillModel
    will then use its built-in default profile).
    """
    bars = enhanced.intraday_bars
    if not bars or len(bars) < bins:
        return None

    # Group volumes by time bin (assuming bars span a trading day)
    total_vol = sum(b.volume for b in bars)
    if total_vol <= 0:
        return None

    # Take last `bins` bars and normalize
    recent = bars[-bins:]
    profile = [b.volume / total_vol for b in recent]

    # Normalize to sum to 1.0
    profile_sum = sum(profile)
    if profile_sum > 0:
        profile = [p / profile_sum for p in profile]

    return profile


def extract_impact_inputs(
    enhanced: EnhancedMarketData,
    fallback_adv: float = 0.0,
    fallback_price: float = 0.0,
    fallback_volatility: float = 0.02,
) -> dict[str, float]:
    """
    Extract inputs for ``MarketImpactModel.estimate_impact()``.

    Returns:
      - adv: Average daily volume
      - price: Current price
      - daily_volatility: Estimated daily return volatility
    """
    liquidity = enhanced.liquidity or LiquiditySnapshot.empty(enhanced.ticker)

    adv = liquidity.avg_daily_volume_30d or fallback_adv

    price = enhanced.last_trade_price or fallback_price
    if not price and enhanced.intraday_bars:
        price = enhanced.intraday_bars[-1].close

    # Estimate daily volatility from intraday bars
    volatility = fallback_volatility
    if len(enhanced.intraday_bars) >= 5:
        closes = [b.close for b in enhanced.intraday_bars if b.close > 0]
        if len(closes) >= 5:
            returns = [
                (closes[i] - closes[i - 1]) / closes[i - 1]
                for i in range(1, len(closes))
                if closes[i - 1] > 0
            ]
            if returns:
                mean_r = sum(returns) / len(returns)
                variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
                volatility = variance ** 0.5

    return {
        "adv": adv,
        "price": price or 0.0,
        "daily_volatility": volatility,
    }
