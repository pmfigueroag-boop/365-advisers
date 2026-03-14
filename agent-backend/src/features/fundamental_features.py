"""
src/features/fundamental_features.py
──────────────────────────────────────────────────────────────────────────────
Extracts and normalises fundamental features from FinancialStatements.

Key responsibilities:
  - Convert "DATA_INCOMPLETE" strings to None
  - Derive composite metrics (margin trend, earnings stability, debt/ebitda)
  - Produce a clean FundamentalFeatureSet ready for the Fundamental Engine
"""

from __future__ import annotations

import logging
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


def extract_fundamental_features(financials: FinancialStatements) -> FundamentalFeatureSet:
    """
    Transform raw FinancialStatements into a normalised FundamentalFeatureSet.

    All "DATA_INCOMPLETE" strings are converted to None.
    Derived metrics (margin_trend, earnings_stability, debt_to_ebitda) are
    computed when sufficient data is available.
    """
    r = financials.ratios
    p = r.profitability
    v = r.valuation
    l = r.leverage
    q = r.quality

    # ── Derive margin trend from cashflow series ──────────────────────────────
    margin_trend: float | None = None
    series = financials.cashflow_series
    if len(series) >= 2:
        try:
            latest_rev = series[-1].revenue
            earliest_rev = series[0].revenue
            latest_fcf = series[-1].fcf
            earliest_fcf = series[0].fcf
            if earliest_rev and latest_rev and earliest_rev > 0 and latest_rev > 0:
                latest_margin = latest_fcf / latest_rev
                earliest_margin = earliest_fcf / earliest_rev
                margin_trend = latest_margin - earliest_margin
        except (ZeroDivisionError, TypeError):
            pass

    # ── Derive earnings stability from beta + earnings growth ─────────────────
    beta = _to_float(q.beta)
    eg = _to_float(q.earnings_growth_yoy)
    earnings_stability: float | None = None
    if beta is not None:
        # Lower beta + moderate growth = higher stability
        stability_raw = 10.0 - min(abs(beta - 1.0) * 3.0, 5.0)
        if eg is not None and eg < -0.2:  # declining earnings penalise stability
            stability_raw -= 2.0
        earnings_stability = max(0.0, min(10.0, stability_raw))

    # ── Derive debt/EBITDA proxy (if ev_ebitda available) ─────────────────────
    ev_ebitda = _to_float(v.ev_ebitda)
    dte = _to_float(l.debt_to_equity)
    debt_to_ebitda: float | None = None
    if ev_ebitda is not None and dte is not None and ev_ebitda > 0:
        # Rough proxy: D/EBITDA ≈ D/E × (EV/EBITDA) / (EV/E)
        # Simplified: just use EV/EBITDA as a leverage proxy scaled by D/E
        debt_to_ebitda = dte * ev_ebitda / max(ev_ebitda, 1.0) if dte else None

    return FundamentalFeatureSet(
        ticker=financials.ticker,
        name=financials.name,
        sector=financials.sector,
        industry=financials.industry,
        description=financials.description,
        market_cap=v.market_cap,

        # Profitability
        roic=_to_float(p.roic),
        roe=_to_float(p.roe),
        gross_margin=_to_float(p.gross_margin),
        ebit_margin=_to_float(p.ebit_margin),
        net_margin=_to_float(p.net_margin),

        # Cash Flow
        fcf_yield=_to_float(v.fcf_yield),

        # Leverage
        debt_to_equity=dte,
        debt_to_ebitda=debt_to_ebitda,
        current_ratio=_to_float(l.current_ratio),
        quick_ratio=_to_float(l.quick_ratio),

        # Growth
        revenue_growth_yoy=_to_float(q.revenue_growth_yoy),
        earnings_growth_yoy=_to_float(q.earnings_growth_yoy),

        # Valuation
        pe_ratio=_to_float(v.pe_ratio),
        pb_ratio=_to_float(v.pb_ratio),
        ev_ebitda=ev_ebitda if ev_ebitda is None else _to_float(v.ev_ebitda),

        # Quality
        dividend_yield=q.dividend_yield,
        payout_ratio=q.payout_ratio,
        beta=beta,

        # Derived
        margin_trend=margin_trend,
        earnings_stability=earnings_stability,

        # C4: Sector-relative P/E adjustment
        sector_pe_adjustment=_sector_pe_factor(financials.sector),

        # C6: Fundamental momentum / acceleration
        revenue_acceleration=_compute_revenue_acceleration(financials.cashflow_series),
        margin_expansion_rate=margin_trend,  # reuse margin trend as the rate
    )


# ── C4: Sector-relative P/E adjustment factors ──────────────────────────────
# Multipliers applied to P/E thresholds by sector. > 1.0 means the sector
# typically has higher P/E (so value thresholds should be relaxed).
_SECTOR_PE_FACTORS = {
    "Technology": 1.8,
    "Communication Services": 1.5,
    "Healthcare": 1.4,
    "Consumer Cyclical": 1.3,
    "Consumer Defensive": 1.1,
    "Financial Services": 0.9,
    "Industrials": 1.1,
    "Energy": 0.7,
    "Utilities": 0.8,
    "Real Estate": 1.0,
    "Basic Materials": 0.9,
}


def _sector_pe_factor(sector: str) -> float:
    """Return the P/E adjustment factor for the given sector."""
    return _SECTOR_PE_FACTORS.get(sector, 1.0)


# ── C6: Revenue acceleration ────────────────────────────────────────────────
def _compute_revenue_acceleration(cashflow_series: list) -> float | None:
    """Compute revenue acceleration (change in growth rate) from cashflow."""
    if len(cashflow_series) < 3:
        return None
    try:
        revs = [e.revenue for e in cashflow_series[-3:] if e.revenue and e.revenue > 0]
        if len(revs) < 3:
            return None
        g1 = (revs[-2] - revs[-3]) / revs[-3]  # Earlier growth rate
        g2 = (revs[-1] - revs[-2]) / revs[-2]  # Recent growth rate
        return round(g2 - g1, 6)  # Positive = accelerating
    except (ZeroDivisionError, TypeError, AttributeError):
        return None
