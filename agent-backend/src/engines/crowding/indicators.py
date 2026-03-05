"""
src/engines/crowding/indicators.py
──────────────────────────────────────────────────────────────────────────────
Individual crowding indicator calculators.

Each function takes raw market data and returns a normalised score [0, 1].
Functions gracefully return 0.0 when input data is insufficient.
"""

from __future__ import annotations

import math
import logging

import pandas as pd

logger = logging.getLogger("365advisers.crowding.indicators")


def compute_volume_anomaly(
    ohlcv: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 60,
) -> float:
    """
    Volume Anomaly Score (VAS).

    VAS = clip( (Vol_short / Vol_long − 1) / σ_vol , 0, 1 )

    Parameters
    ----------
    ohlcv : pd.DataFrame
        Must contain a 'Volume' column.
    short_window : int
        Short moving average window (default 20).
    long_window : int
        Long moving average window (default 60).

    Returns
    -------
    float
        VAS in [0, 1].
    """
    if ohlcv is None or ohlcv.empty or "Volume" not in ohlcv.columns:
        return 0.0

    vol = ohlcv["Volume"].dropna()
    if len(vol) < long_window:
        return 0.0

    vol_short = vol.tail(short_window).mean()
    vol_long = vol.tail(long_window).mean()

    if vol_long <= 0:
        return 0.0

    # Rolling volume ratio std
    ratios = vol.rolling(short_window).mean() / vol.rolling(long_window).mean()
    sigma = ratios.dropna().std()

    if sigma <= 0 or math.isnan(sigma):
        return 0.0

    ratio = (vol_short / vol_long) - 1.0
    vas = ratio / sigma

    return max(0.0, min(1.0, vas))


def compute_etf_flow_concentration(
    net_flows_5d: float = 0.0,
    mean_flow_60d: float = 0.0,
    std_flow_60d: float = 1.0,
) -> float:
    """
    ETF Flow Concentration (EFC).

    EFC = clip( net_flow_z_score / 2.0 , 0, 1 )

    Parameters
    ----------
    net_flows_5d : float
        Net ETF flows over the last 5 days.
    mean_flow_60d : float
        60-day mean of net flows.
    std_flow_60d : float
        60-day std of net flows.

    Returns
    -------
    float
        EFC in [0, 1].
    """
    if std_flow_60d <= 0:
        return 0.0

    z_score = (net_flows_5d - mean_flow_60d) / std_flow_60d
    efc = z_score / 2.0

    return max(0.0, min(1.0, efc))


def compute_institutional_herding(
    inst_ownership_change: float = 0.0,
    sector_avg_change: float = 0.0,
) -> float:
    """
    Institutional Ownership Herding (IOH).

    IOH = clip( Δ_inst / avg_Δ_inst , 0, 1 )

    Parameters
    ----------
    inst_ownership_change : float
        Quarter-over-quarter change in institutional ownership %.
    sector_avg_change : float
        Sector average QoQ change.

    Returns
    -------
    float
        IOH in [0, 1].
    """
    if sector_avg_change <= 0:
        return 0.0

    ioh = inst_ownership_change / sector_avg_change

    return max(0.0, min(1.0, ioh))


def compute_volatility_compression(
    ohlcv: pd.DataFrame | None = None,
    realized_vol_20d: float | None = None,
    implied_vol_30d: float | None = None,
) -> float:
    """
    Volatility Compression (VC).

    VC = clip( 1 − (RealVol₂₀ / ImpliedVol₃₀) , 0, 1 )

    Can compute realized vol from OHLCV if not provided directly.

    Parameters
    ----------
    ohlcv : pd.DataFrame | None
        Price data with 'Close' column.
    realized_vol_20d : float | None
        Pre-computed 20-day realized vol (annualised).
    implied_vol_30d : float | None
        30-day implied vol (annualised). Required.

    Returns
    -------
    float
        VC in [0, 1].
    """
    # Compute realized vol from OHLCV if not provided
    if realized_vol_20d is None and ohlcv is not None and not ohlcv.empty:
        if "Close" in ohlcv.columns and len(ohlcv) >= 21:
            returns = ohlcv["Close"].pct_change().dropna().tail(20)
            realized_vol_20d = float(returns.std() * math.sqrt(252))

    if realized_vol_20d is None or implied_vol_30d is None:
        return 0.0
    if implied_vol_30d <= 0:
        return 0.0

    vc = 1.0 - (realized_vol_20d / implied_vol_30d)

    return max(0.0, min(1.0, vc))
