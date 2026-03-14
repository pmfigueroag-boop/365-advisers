"""
src/features/technical_features.py
──────────────────────────────────────────────────────────────────────────────
Extracts and normalises technical features from PriceHistory + MarketMetrics.

Key responsibilities:
  - Map RawIndicators into the TechnicalFeatureSet schema
  - Compute derived features with statistical rigor:
    · volume_surprise (z-score), relative_volume (ratio)
    · pct_from_52w_high (price cycle)
    · mean_reversion_z (log-price z-score)
  - Produce a clean TechnicalFeatureSet ready for the Technical Engine
"""

from __future__ import annotations

import logging
import math
from src.contracts.market_data import PriceHistory, MarketMetrics
from src.contracts.features import TechnicalFeatureSet

logger = logging.getLogger("365advisers.features.technical")


def extract_technical_features(
    price_history: PriceHistory,
    market_metrics: MarketMetrics,
) -> TechnicalFeatureSet:
    """
    Transform PriceHistory + MarketMetrics into a normalised TechnicalFeatureSet.

    This layer decouples the Technical Engine from the specific data source
    format (TradingView, yfinance, or any future provider).
    """
    ind = market_metrics.indicators
    bars = [bar.model_dump() for bar in price_history.ohlcv]
    current_price = price_history.current_price or ind.close

    # ── Volume intelligence (upgraded from basic avg to z-score + ratio) ──
    volume_avg_20, volume_surprise, relative_volume = _compute_volume_features(
        bars, ind.volume
    )

    # F1: Winsorize outlier-prone values
    volume_surprise = max(-5.0, min(5.0, volume_surprise))    # clip z-score to ±5σ
    rsi = max(0.0, min(100.0, ind.rsi))                       # definition bounds
    stoch_k = max(0.0, min(100.0, ind.stoch_k))
    stoch_d = max(0.0, min(100.0, ind.stoch_d))

    # Compute price cycle features
    pct_52w = _compute_pct_from_52w_high(bars, current_price)
    mr_z = _compute_mean_reversion_z_log(bars, current_price)
    # F1: Winsorize z-score
    if mr_z is not None:
        mr_z = max(-5.0, min(5.0, mr_z))

    # F2: Completeness score (fraction of meaningful non-zero features)
    feature_vals = [current_price, ind.sma50, ind.sma200, rsi, ind.macd,
                    ind.atr, volume_avg_20, ind.obv]
    non_zero = sum(1 for v in feature_vals if v and v != 0)
    completeness = round(non_zero / len(feature_vals), 3)

    return TechnicalFeatureSet(
        ticker=price_history.ticker,
        current_price=current_price,

        # Moving Averages
        sma_50=ind.sma50,
        sma_200=ind.sma200,
        ema_20=ind.ema20,

        # Momentum (F1: winsorized)
        rsi=rsi,
        stoch_k=stoch_k,
        stoch_d=stoch_d,

        # MACD
        macd=ind.macd,
        macd_signal=ind.macd_signal,
        macd_hist=ind.macd_hist,

        # Volatility
        bb_upper=ind.bb_upper,
        bb_lower=ind.bb_lower,
        bb_basis=ind.bb_basis,
        atr=ind.atr,

        # Volume (upgraded + F1: winsorized)
        volume=ind.volume,
        obv=ind.obv,
        volume_avg_20=volume_avg_20,
        volume_surprise=volume_surprise,
        relative_volume=relative_volume,

        # Raw bars for structure analysis
        ohlcv=bars,

        # Regime detection
        adx=getattr(ind, "adx", 20.0) or 20.0,
        plus_di=getattr(ind, "plus_di", 20.0) or 20.0,
        minus_di=getattr(ind, "minus_di", 20.0) or 20.0,

        # TradingView consensus
        tv_recommendation=ind.tv_recommendation,

        # C7: Price cycle positioning (F1: winsorized)
        pct_from_52w_high=pct_52w,
        mean_reversion_z=mr_z,

        # F2: Feature validation
        completeness_score=completeness,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Volume intelligence (upgraded from basic average)
# ═════════════════════════════════════════════════════════════════════════════

def _compute_volume_features(
    bars: list[dict], current_volume: float
) -> tuple[float, float, float]:
    """
    Compute three volume features from OHLCV bars:

    Returns (volume_avg_20, volume_surprise, relative_volume).

    - volume_avg_20:  mean(last 20 bars volume)
    - volume_surprise: (current - mean_20) / std_20  — z-score
    - relative_volume:  current / mean_20  — ratio (>1 = above average)
    """
    if len(bars) < 20:
        return 0.0, 0.0, 1.0

    recent_vols = [b.get("volume", 0) for b in bars[-20:] if b.get("volume")]
    if not recent_vols or len(recent_vols) < 10:
        return 0.0, 0.0, 1.0

    n = len(recent_vols)
    mean_vol = sum(recent_vols) / n
    std_vol = (sum((v - mean_vol) ** 2 for v in recent_vols) / n) ** 0.5

    # volume_surprise (z-score)
    vol_surprise = 0.0
    if std_vol > 0 and current_volume > 0:
        vol_surprise = round((current_volume - mean_vol) / std_vol, 4)

    # relative_volume (ratio)
    rel_vol = 1.0
    if mean_vol > 0 and current_volume > 0:
        rel_vol = round(current_volume / mean_vol, 4)

    return round(mean_vol, 2), vol_surprise, rel_vol


# ═════════════════════════════════════════════════════════════════════════════
# Price cycle features
# ═════════════════════════════════════════════════════════════════════════════

def _compute_pct_from_52w_high(bars: list[dict], current_price: float) -> float | None:
    """How far current price is from 52-week high (negative = below)."""
    if not bars or current_price <= 0:
        return None
    highs = [b.get("high", 0) for b in bars[-252:] if b.get("high")]
    if not highs:
        return None
    high_52w = max(highs)
    if high_52w <= 0:
        return None
    return round((current_price - high_52w) / high_52w, 6)


def _compute_mean_reversion_z_log(bars: list[dict], current_price: float) -> float | None:
    """
    Z-score of log(price) vs 1-year rolling mean of log(price).

    Using log-price instead of raw price reduces bias from
    non-stationarity and heteroscedasticity in price levels.
    This is the standard approach in quantitative finance.

    z = (log(price) - mean(log(prices))) / std(log(prices))
    """
    if not bars or current_price <= 0:
        return None
    closes = [b.get("close", 0) for b in bars[-252:] if b.get("close") and b.get("close") > 0]
    if len(closes) < 50:
        return None

    # Log transform
    log_prices = [math.log(c) for c in closes]
    log_current = math.log(current_price)

    avg = sum(log_prices) / len(log_prices)
    std = (sum((lp - avg) ** 2 for lp in log_prices) / len(log_prices)) ** 0.5
    if std <= 0:
        return None
    return round((log_current - avg) / std, 4)
