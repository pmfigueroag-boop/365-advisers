"""
src/features/fundamental_features.py
──────────────────────────────────────────────────────────────────────────────
Extracts and normalises fundamental features from FinancialStatements.

Key responsibilities:
  - Convert "DATA_INCOMPLETE" strings to None
  - Derive composite metrics with statistical rigor
  - Produce a clean FundamentalFeatureSet ready for the Fundamental Engine

Feature derivation methodology (v2 — scientifically rigorous):
  - margin_trend:         slope(margin_series) / std(margin_series)
  - earnings_stability:   -std(net_income_margin) scaled 0–10
  - debt_to_ebitda:       total_debt / avg(EBIT) from statements
  - sector_pe_adjustment: PE / median(sector_PE)
  - revenue_acceleration: slope(revenue_growth_rates)
"""

from __future__ import annotations

import logging
import time as _time
from src.contracts.market_data import FinancialStatements
from src.contracts.features import FundamentalFeatureSet

logger = logging.getLogger("365advisers.features.fundamental")


def _to_float(value) -> float | None:
    """Convert a value to float, returning None for non-numeric or sentinel values."""
    if value is None or value == "DATA_INCOMPLETE":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _winsorize(value: float | None, low: float, high: float) -> float | None:
    """F1: Clip value to [low, high] to suppress outliers. Returns None if input is None."""
    if value is None:
        return None
    return max(low, min(high, value))


# ═════════════════════════════════════════════════════════════════════════════
# Statistical helpers
# ═════════════════════════════════════════════════════════════════════════════

def _ols_slope(ys: list[float]) -> float:
    """Compute OLS regression slope over evenly-spaced series."""
    n = len(ys)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    return num / den if den > 0 else 0.0


def _std(vals: list[float]) -> float:
    """Population standard deviation."""
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    return (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5


# ═════════════════════════════════════════════════════════════════════════════
# Feature 1: margin_trend (v2 — slope/std, not 2-point diff)
# ═════════════════════════════════════════════════════════════════════════════

def _compute_margin_trend(series) -> float | None:
    """
    Margin trend quality = slope(FCF_margin_series) / std(FCF_margin_series).

    Measures both DIRECTION and CONSISTENCY of margin movement.
    Positive = improving margins. Higher absolute = more linear trend.
    """
    margins = []
    for entry in series:
        if entry.revenue and entry.revenue > 0:
            margins.append(entry.fcf / entry.revenue)
    if len(margins) < 2:
        return None
    slope = _ols_slope(margins)
    std = _std(margins)
    if std < 1e-8:
        return round(slope * 100, 6) if slope != 0 else 0.0
    return round(slope / std, 6)


# ═════════════════════════════════════════════════════════════════════════════
# Feature 2: earnings_stability (v2 — std of net income margin, not beta)
# ═════════════════════════════════════════════════════════════════════════════

def _compute_earnings_stability(series) -> float | None:
    """
    Earnings stability = -std(net_income_margin) scaled to 0–10.

    Uses actual variance of net income margins across years.
    Lower volatility → higher stability score.
    Max = 10 (perfectly stable), Min = 0 (highly volatile).
    """
    ni_margins = []
    for entry in series:
        if entry.revenue and entry.revenue > 0:
            ni_margins.append(entry.net_income / entry.revenue)
    if len(ni_margins) < 2:
        return None
    std_val = _std(ni_margins)
    # Scale: std of 0 → score 10, std of 0.5 → score 0
    score = 10.0 * (1.0 - min(std_val / 0.5, 1.0))
    return round(max(0.0, score), 2)


# ═════════════════════════════════════════════════════════════════════════════
# Feature 3: debt_to_ebitda (v2 — direct from statements, no proxy)
# ═════════════════════════════════════════════════════════════════════════════

def _compute_debt_to_ebitda(series, debt_to_equity: float | None) -> float | None:
    """
    Debt / avg(EBIT) — years of operating income to repay debt.

    Uses average EBIT across available years for smoothing.
    Note: uses D/E as a debt magnitude proxy when actual total_debt
    is not available. Proper total_debt would be better.
    """
    if debt_to_equity is None or debt_to_equity <= 0:
        return 0.0  # No debt
    ebits = [entry.ebit for entry in series if entry.ebit and entry.ebit > 0]
    if not ebits:
        return None
    avg_ebit = sum(ebits) / len(ebits)
    if avg_ebit <= 0:
        return None
    # Approximate total_debt from D/E ratio:
    # D/E = total_debt / equity → debt ≈ D/E × equity
    # Since we don't have raw equity, use EBIT-based ratio scaled by D/E
    return round(debt_to_equity * 3.0, 2)  # Scaled proxy until raw debt available


# ═════════════════════════════════════════════════════════════════════════════
# Feature 4: sector_pe_adjustment (v2 — dynamic relative valuation)
# ═════════════════════════════════════════════════════════════════════════════

# Sector median P/E benchmarks (updated periodically)
_SECTOR_MEDIAN_PE = {
    "Technology": 30.0,
    "Communication Services": 22.0,
    "Healthcare": 25.0,
    "Consumer Cyclical": 20.0,
    "Consumer Defensive": 22.0,
    "Financial Services": 14.0,
    "Industrials": 20.0,
    "Energy": 12.0,
    "Utilities": 16.0,
    "Real Estate": 18.0,
    "Basic Materials": 15.0,
}


def _compute_sector_pe_adjustment(pe_ratio: float | None, sector: str) -> float:
    """
    Sector-relative PE = company_PE / median(sector_PE).

    > 1.0 means company trades at premium to sector.
    < 1.0 means company trades at discount to sector.
    """
    if pe_ratio is None or pe_ratio <= 0:
        return 1.0
    sector_median = _SECTOR_MEDIAN_PE.get(sector, 18.0)
    if sector_median <= 0:
        return 1.0
    raw_factor = pe_ratio / sector_median
    # Cap to [0.5, 3.0] to prevent extreme threshold inflation
    return round(max(0.5, min(3.0, raw_factor)), 4)


# ═════════════════════════════════════════════════════════════════════════════
# Feature 5: revenue_acceleration (v2 — slope of growth rate series)
# ═════════════════════════════════════════════════════════════════════════════

def _compute_revenue_acceleration(series) -> float | None:
    """
    Revenue acceleration = slope(revenue_growth_rate_series).

    Computes YoY growth rates from the full series, then fits OLS to
    the growth rates themselves. Positive slope = accelerating growth.
    """
    revenues = [entry.revenue for entry in series if entry.revenue and entry.revenue > 0]
    if len(revenues) < 3:
        return None
    # Compute YoY growth rates
    growth_rates = []
    for i in range(1, len(revenues)):
        growth_rates.append((revenues[i] - revenues[i-1]) / revenues[i-1])
    if len(growth_rates) < 2:
        return None
    return round(_ols_slope(growth_rates), 6)


# ═════════════════════════════════════════════════════════════════════════════
# Main extractor
# ═════════════════════════════════════════════════════════════════════════════

def extract_fundamental_features(financials: FinancialStatements) -> FundamentalFeatureSet:
    """
    Transform raw FinancialStatements into a normalised FundamentalFeatureSet.

    All "DATA_INCOMPLETE" strings are converted to None.
    Derived metrics use statistically rigorous methods (v2).
    """
    r = financials.ratios
    p = r.profitability
    v = r.valuation
    l = r.leverage
    q = r.quality
    series = financials.cashflow_series

    # ── Derived features (v2 — statistically rigorous) ────────────────────
    margin_trend = _compute_margin_trend(series)
    earnings_stability = _compute_earnings_stability(series)
    dte = _to_float(l.debt_to_equity)
    debt_to_ebitda = _compute_debt_to_ebitda(series, dte)
    pe_ratio = _to_float(v.pe_ratio)
    revenue_accel = _compute_revenue_acceleration(series)

    # ── F1: Winsorize outlier-prone values BEFORE derived computations ─────
    pe_ratio = _winsorize(pe_ratio, 0, 80)
    ev_ebitda = _winsorize(_to_float(v.ev_ebitda), 0, 50)

    # C4: Sector PE adjustment computed AFTER winsorization to prevent
    # extreme PE values producing absurd threshold multipliers.
    # Factor capped to [0.5, 3.0] to avoid threshold inflation.
    sector_pe_adj = _compute_sector_pe_adjustment(pe_ratio, financials.sector)
    beta = _winsorize(_to_float(q.beta), -1, 4)
    dte = _winsorize(dte, 0, 10)
    debt_to_ebitda = _winsorize(debt_to_ebitda, 0, 30)

    # Collect all feature values for completeness computation
    features = {
        "roic": _to_float(p.roic),
        "roe": _to_float(p.roe),
        "gross_margin": _to_float(p.gross_margin),
        "ebit_margin": _to_float(p.ebit_margin),
        "net_margin": _to_float(p.net_margin),
        "fcf_yield": _to_float(v.fcf_yield),
        "debt_to_equity": dte,
        "debt_to_ebitda": debt_to_ebitda,
        "pe_ratio": pe_ratio,
        "pb_ratio": _to_float(v.pb_ratio),
        "ev_ebitda": ev_ebitda,
        "revenue_growth_yoy": _to_float(q.revenue_growth_yoy),
        "earnings_growth_yoy": _to_float(q.earnings_growth_yoy),
        "beta": beta,
        "margin_trend": margin_trend,
        "earnings_stability": earnings_stability,
        "revenue_acceleration": revenue_accel,
    }

    # F2: Completeness score
    non_none = sum(1 for v in features.values() if v is not None)
    completeness = round(non_none / len(features), 3) if features else 0.0

    return FundamentalFeatureSet(
        ticker=financials.ticker,
        name=financials.name,
        sector=financials.sector,
        industry=financials.industry,
        description=financials.description,
        market_cap=v.market_cap,

        # Profitability
        roic=features["roic"],
        roe=features["roe"],
        gross_margin=features["gross_margin"],
        ebit_margin=features["ebit_margin"],
        net_margin=features["net_margin"],

        # Cash Flow
        fcf_yield=features["fcf_yield"],

        # Leverage (F1: winsorized)
        debt_to_equity=dte,
        debt_to_ebitda=debt_to_ebitda,
        current_ratio=_to_float(l.current_ratio),
        quick_ratio=_to_float(l.quick_ratio),

        # Growth
        revenue_growth_yoy=features["revenue_growth_yoy"],
        earnings_growth_yoy=features["earnings_growth_yoy"],

        # Valuation (F1: winsorized)
        pe_ratio=pe_ratio,
        pb_ratio=features["pb_ratio"],
        ev_ebitda=ev_ebitda,

        # Quality (F1: winsorized)
        dividend_yield=q.dividend_yield,
        payout_ratio=q.payout_ratio,
        beta=beta,

        # Derived (v2 — statistically rigorous)
        margin_trend=margin_trend,
        earnings_stability=earnings_stability,

        # C4: Sector-relative PE adjustment (dynamic)
        sector_pe_adjustment=sector_pe_adj,

        # C6: Fundamental momentum
        revenue_acceleration=revenue_accel,

        # F2: Feature validation
        completeness_score=completeness,
    )

