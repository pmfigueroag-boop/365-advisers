"""
src/engines/ml_signals/feature_engineering.py
──────────────────────────────────────────────────────────────────────────────
Feature engineering pipeline for ML signal generation.

Builds a flat feature vector from the existing FundamentalFeatureSet
and TechnicalFeatureSet contracts, handling None imputation and
z-score normalisation.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet

logger = logging.getLogger("365advisers.ml_signals.feature_engineering")


def build_feature_vector(
    fundamental: FundamentalFeatureSet | None = None,
    technical: TechnicalFeatureSet | None = None,
) -> dict[str, float]:
    """
    Build a flat feature dictionary from Fundamental + Technical feature sets.

    Extracts ~30 numeric features, handles None→0.0 imputation, and returns
    a dict ready for pandas DataFrame ingestion or direct numpy conversion.

    Args:
        fundamental: Normalised fundamental features (may be None).
        technical: Normalised technical features (may be None).

    Returns:
        Dict mapping feature_name → float value.
    """
    features: dict[str, float] = {}

    # ── Fundamental Features ─────────────────────────────────────────────
    if fundamental:
        features.update({
            # Profitability
            "roic": _safe(fundamental.roic),
            "roe": _safe(fundamental.roe),
            "gross_margin": _safe(fundamental.gross_margin),
            "ebit_margin": _safe(fundamental.ebit_margin),
            "net_margin": _safe(fundamental.net_margin),
            # Cash Flow
            "fcf_yield": _safe(fundamental.fcf_yield),
            # Leverage
            "debt_to_equity": _safe(fundamental.debt_to_equity),
            "current_ratio": _safe(fundamental.current_ratio),
            # Growth
            "revenue_growth_yoy": _safe(fundamental.revenue_growth_yoy),
            "earnings_growth_yoy": _safe(fundamental.earnings_growth_yoy),
            # Valuation
            "pe_ratio": _safe(fundamental.pe_ratio),
            "pb_ratio": _safe(fundamental.pb_ratio),
            "ev_ebitda": _safe(fundamental.ev_ebitda),
            # Quality
            "dividend_yield": _safe(fundamental.dividend_yield),
            "beta": _safe(fundamental.beta, default=1.0),
            # Trend
            "margin_trend": _safe(fundamental.margin_trend),
            "earnings_stability": _safe(fundamental.earnings_stability),
        })

    # ── Technical Features ───────────────────────────────────────────────
    if technical:
        price = max(technical.current_price, 0.01)
        features.update({
            # Moving Average ratios (normalised by price)
            "price_to_sma50": price / max(technical.sma_50, 0.01) if technical.sma_50 else 1.0,
            "price_to_sma200": price / max(technical.sma_200, 0.01) if technical.sma_200 else 1.0,
            "sma50_to_sma200": (
                technical.sma_50 / max(technical.sma_200, 0.01)
                if technical.sma_50 and technical.sma_200 else 1.0
            ),
            # Momentum
            "rsi": technical.rsi,
            "stoch_k": technical.stoch_k,
            "macd_hist": technical.macd_hist,
            # Volatility
            "bb_width": (
                (technical.bb_upper - technical.bb_lower) / max(technical.bb_basis, 0.01)
                if technical.bb_basis else 0.0
            ),
            "atr_pct": technical.atr / price * 100 if technical.atr else 0.0,
            # Volume
            "volume_ratio": (
                technical.volume / max(technical.volume_avg_20, 1.0)
                if technical.volume_avg_20 else 1.0
            ),
            "obv_normalised": technical.obv / max(abs(technical.volume_avg_20), 1.0),
        })

    # ── Derived / Interaction Features ───────────────────────────────────
    if fundamental and technical:
        # Value-momentum composite
        pe = _safe(fundamental.pe_ratio)
        rsi = technical.rsi if technical else 50.0
        if pe > 0:
            features["value_momentum"] = (1.0 / pe) * (rsi / 50.0)
        else:
            features["value_momentum"] = 0.0

        # Quality-trend composite
        roic = _safe(fundamental.roic)
        margin_trend = _safe(fundamental.margin_trend)
        features["quality_trend"] = roic * (1 + margin_trend) if roic else 0.0

    return features


def normalise_features(
    feature_vectors: list[dict[str, float]],
) -> list[dict[str, float]]:
    """
    Z-score normalise a list of feature vectors (cross-sectional).

    For each feature, computes (x - mean) / std across all vectors.
    """
    if not feature_vectors:
        return []

    # Collect all feature names
    all_keys = set()
    for fv in feature_vectors:
        all_keys.update(fv.keys())

    # Compute mean and std per feature
    stats: dict[str, tuple[float, float]] = {}
    for key in all_keys:
        values = [fv.get(key, 0.0) for fv in feature_vectors]
        arr = np.array(values, dtype=np.float64)
        mean = float(np.nanmean(arr))
        std = float(np.nanstd(arr))
        stats[key] = (mean, max(std, 1e-10))

    # Normalise
    normalised = []
    for fv in feature_vectors:
        norm_fv = {}
        for key in all_keys:
            val = fv.get(key, 0.0)
            mean, std = stats[key]
            norm_fv[key] = (val - mean) / std
        normalised.append(norm_fv)

    return normalised


def _safe(value: float | None, default: float = 0.0) -> float:
    """Convert None to a default float value."""
    if value is None:
        return default
    if not np.isfinite(value):
        return default
    return float(value)
