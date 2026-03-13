"""
src/engines/technical/calibration.py
──────────────────────────────────────────────────────────────────────────────
Self-calibrating indicator normalisation from OHLCV history.

No hard-coded "normal" ATR% or volume thresholds — the asset calibrates
itself from its own historical distribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass
class AssetContext:
    """Self-calibrated context from the asset's own OHLCV history."""
    optimal_atr_pct: float = 1.8       # median ATR% (replaces hard-coded 1.8)
    atr_iqr: float = 1.0               # interquartile range of ATR%
    volume_median: float = 1_000_000   # median daily volume
    volume_iqr: float = 500_000        # interquartile range of volume
    bb_width_median: float = 4.0       # median BB width %
    bb_width_iqr: float = 2.0          # IQR of BB width %
    avg_daily_range_pct: float = 2.0   # median daily range as pct of price
    bars_available: int = 0             # how many bars were used


def compute_asset_context(ohlcv: list[dict], price: float = 0.0) -> AssetContext:
    """
    Compute self-calibrating asset context from OHLCV history.

    Uses percentiles of ATR%, volume, and BB width to establish what
    is "normal" for this specific asset. No external data needed.

    Args:
        ohlcv: List of OHLCV candle dicts with open/high/low/close/volume.
        price: Current price for percentage calculations.

    Returns:
        AssetContext with calibrated thresholds.
    """
    if not ohlcv or len(ohlcv) < 14:
        return AssetContext()

    closes = [b.get("close", 0) for b in ohlcv if b.get("close", 0) > 0]
    highs  = [b.get("high", 0) for b in ohlcv if b.get("high", 0) > 0]
    lows   = [b.get("low", 0) for b in ohlcv if b.get("low", 0) > 0]
    vols   = [b.get("volume", 0) for b in ohlcv if b.get("volume", 0) > 0]

    if len(closes) < 14:
        return AssetContext()

    # ── ATR% series ──────────────────────────────────────────────────────
    atr_pct_values = []
    for i in range(1, min(len(closes), len(highs), len(lows))):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        if closes[i] > 0:
            atr_pct_values.append((tr / closes[i]) * 100)

    # ── Daily range series ───────────────────────────────────────────────
    daily_range_pct = []
    for i in range(len(min(highs, lows, key=len))):
        if closes[i] > 0 and i < len(highs) and i < len(lows):
            dr = (highs[i] - lows[i]) / closes[i] * 100
            daily_range_pct.append(dr)

    # ── BB width proxy (20-period range) ─────────────────────────────────
    bb_width_pct = []
    for i in range(20, len(closes)):
        window = closes[i - 20:i]
        mean = sum(window) / 20
        if mean > 0:
            std = math.sqrt(sum((x - mean) ** 2 for x in window) / 20)
            bb_width_pct.append((std * 4 / mean) * 100)  # ~4σ width

    return AssetContext(
        optimal_atr_pct=_percentile(atr_pct_values, 50) if atr_pct_values else 1.8,
        atr_iqr=(_percentile(atr_pct_values, 75) - _percentile(atr_pct_values, 25)) if len(atr_pct_values) > 3 else 1.0,
        volume_median=_percentile(vols, 50) if vols else 1_000_000,
        volume_iqr=(_percentile(vols, 75) - _percentile(vols, 25)) if len(vols) > 3 else 500_000,
        bb_width_median=_percentile(bb_width_pct, 50) if bb_width_pct else 4.0,
        bb_width_iqr=(_percentile(bb_width_pct, 75) - _percentile(bb_width_pct, 25)) if len(bb_width_pct) > 3 else 2.0,
        avg_daily_range_pct=_percentile(daily_range_pct, 50) if daily_range_pct else 2.0,
        bars_available=len(closes),
    )


def _percentile(data: list[float], pct: float) -> float:
    """Compute the given percentile from a sorted list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * pct / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    d = k - f
    return sorted_data[f] + d * (sorted_data[c] - sorted_data[f])


# ─── Asset-Class Defaults (Phase B) ─────────────────────────────────────────

ASSET_CLASS_DEFAULTS: dict[str, AssetContext] = {
    "EQUITY":    AssetContext(optimal_atr_pct=1.8, atr_iqr=1.0, volume_median=5_000_000,
                              volume_iqr=3_000_000, bb_width_median=4.0, bb_width_iqr=2.0,
                              avg_daily_range_pct=2.0),
    "CRYPTO":    AssetContext(optimal_atr_pct=4.5, atr_iqr=3.0, volume_median=50_000_000,
                              volume_iqr=30_000_000, bb_width_median=8.0, bb_width_iqr=4.0,
                              avg_daily_range_pct=5.0),
    "ETF":       AssetContext(optimal_atr_pct=1.2, atr_iqr=0.6, volume_median=20_000_000,
                              volume_iqr=10_000_000, bb_width_median=3.0, bb_width_iqr=1.5,
                              avg_daily_range_pct=1.5),
    "FOREX":     AssetContext(optimal_atr_pct=0.6, atr_iqr=0.3, volume_median=1_000_000,
                              volume_iqr=500_000, bb_width_median=1.5, bb_width_iqr=0.8,
                              avg_daily_range_pct=0.8),
    "COMMODITY": AssetContext(optimal_atr_pct=2.5, atr_iqr=1.5, volume_median=10_000_000,
                              volume_iqr=5_000_000, bb_width_median=5.0, bb_width_iqr=2.5,
                              avg_daily_range_pct=3.0),
}

_CRYPTO_TICKERS = {
    "BTC", "ETH", "SOL", "ADA", "DOGE", "XRP", "DOT", "AVAX", "MATIC",
    "LINK", "UNI", "AAVE", "SHIB", "LTC", "BNB", "ATOM",
}
_ETF_TICKERS = {
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "EEM", "XLF", "XLE",
    "XLK", "GLD", "SLV", "TLT", "HYG", "ARKK", "VXX", "UVXY",
}
_COMMODITY_TICKERS = {
    "GC=F", "SI=F", "CL=F", "NG=F", "ZW=F", "ZC=F",
}


def infer_asset_class(ticker: str) -> str:
    """
    Heuristic asset-class inference from ticker symbol.

    Returns one of: EQUITY, CRYPTO, ETF, FOREX, COMMODITY.
    """
    upper = ticker.upper().replace("-USD", "").replace("USDT", "")

    if upper in _CRYPTO_TICKERS or ticker.endswith("-USD") or ticker.endswith("USDT"):
        return "CRYPTO"
    if upper in _ETF_TICKERS:
        return "ETF"
    if "/" in ticker or upper.endswith("=X"):
        return "FOREX"
    if upper in _COMMODITY_TICKERS or upper.endswith("=F"):
        return "COMMODITY"
    return "EQUITY"


def get_asset_context(
    ohlcv: list[dict],
    ticker: str = "",
    price: float = 0.0,
) -> AssetContext:
    """
    Get the best available asset context:
    1. If enough OHLCV data (≥14 bars), self-calibrate from history
    2. Otherwise, use asset-class defaults based on ticker heuristic
    """
    ctx = compute_asset_context(ohlcv, price)
    if ctx.bars_available >= 14:
        return ctx

    asset_class = infer_asset_class(ticker)
    return ASSET_CLASS_DEFAULTS.get(asset_class, ASSET_CLASS_DEFAULTS["EQUITY"])

