"""
src/features/technical_features.py
──────────────────────────────────────────────────────────────────────────────
Extracts and normalises technical features from PriceHistory + MarketMetrics.

Key responsibilities:
  - Map RawIndicators into the TechnicalFeatureSet schema
  - Compute derived features (volume avg 20, etc.) from OHLCV bars
  - Produce a clean TechnicalFeatureSet ready for the Technical Engine
"""

from __future__ import annotations

import logging
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

    # ── Compute 20-period average volume from OHLCV ───────────────────────────
    volume_avg_20 = 0.0
    if len(bars) >= 20:
        recent_vols = [b.get("volume", 0) for b in bars[-20:] if b.get("volume")]
        if recent_vols:
            volume_avg_20 = sum(recent_vols) / len(recent_vols)

    return TechnicalFeatureSet(
        ticker=price_history.ticker,
        current_price=price_history.current_price or ind.close,

        # Moving Averages
        sma_50=ind.sma50,
        sma_200=ind.sma200,
        ema_20=ind.ema20,

        # Momentum
        rsi=ind.rsi,
        stoch_k=ind.stoch_k,
        stoch_d=ind.stoch_d,

        # MACD
        macd=ind.macd,
        macd_signal=ind.macd_signal,
        macd_hist=ind.macd_hist,

        # Volatility
        bb_upper=ind.bb_upper,
        bb_lower=ind.bb_lower,
        bb_basis=ind.bb_basis,
        atr=ind.atr,

        # Volume
        volume=ind.volume,
        obv=ind.obv,
        volume_avg_20=volume_avg_20,

        # Raw bars for structure analysis
        ohlcv=bars,

        # Regime detection
        adx=getattr(ind, "adx", 20.0) or 20.0,
        plus_di=getattr(ind, "plus_di", 20.0) or 20.0,
        minus_di=getattr(ind, "minus_di", 20.0) or 20.0,

        # TradingView consensus
        tv_recommendation=ind.tv_recommendation,

        # C7: Price cycle positioning from OHLCV bars
        pct_from_52w_high=_compute_pct_from_52w_high(bars, price_history.current_price or ind.close),
        mean_reversion_z=_compute_mean_reversion_z(bars, price_history.current_price or ind.close),
    )


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


def _compute_mean_reversion_z(bars: list[dict], current_price: float) -> float | None:
    """Z-score of current price vs 1-year average (positive = above mean)."""
    if not bars or current_price <= 0:
        return None
    closes = [b.get("close", 0) for b in bars[-252:] if b.get("close")]
    if len(closes) < 50:
        return None
    avg = sum(closes) / len(closes)
    std = (sum((c - avg) ** 2 for c in closes) / len(closes)) ** 0.5
    if std <= 0:
        return None
    return round((current_price - avg) / std, 4)
