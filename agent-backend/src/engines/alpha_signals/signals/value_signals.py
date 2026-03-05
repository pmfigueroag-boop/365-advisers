"""
src/engines/alpha_signals/signals/value_signals.py
──────────────────────────────────────────────────────────────────────────────
Value Alpha Signals — detect undervalued assets based on fundamental
valuation multiples and cash flow metrics.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


VALUE_SIGNALS = [
    AlphaSignalDefinition(
        id="value.fcf_yield_high",
        name="High Free Cash Flow Yield",
        category=SignalCategory.VALUE,
        description="FCF Yield above threshold indicates strong cash generation relative to price",
        feature_path="fundamental.fcf_yield",
        direction=SignalDirection.ABOVE,
        threshold=0.08,
        strong_threshold=0.12,
        weight=1.2,
        tags=["deep_value", "cash_generation"],
    ),
    AlphaSignalDefinition(
        id="value.pe_low",
        name="Low Price to Earnings Relative",
        category=SignalCategory.VALUE,
        description="P/E ratio below historical average indicates potential undervaluation",
        feature_path="fundamental.pe_ratio",
        direction=SignalDirection.BELOW,
        threshold=15.0,
        strong_threshold=10.0,
        weight=1.0,
        tags=["relative_value"],
    ),
    AlphaSignalDefinition(
        id="value.ev_ebitda_low",
        name="Low Enterprise Value to EBITDA",
        category=SignalCategory.VALUE,
        description="EV/EBITDA below threshold suggests cheap enterprise economics",
        feature_path="fundamental.ev_ebitda",
        direction=SignalDirection.BELOW,
        threshold=10.0,
        strong_threshold=7.0,
        weight=1.1,
        tags=["enterprise_value"],
    ),
    AlphaSignalDefinition(
        id="value.pb_low",
        name="Low Price to Book",
        category=SignalCategory.VALUE,
        description="P/B below threshold may indicate asset-based undervaluation",
        feature_path="fundamental.pb_ratio",
        direction=SignalDirection.BELOW,
        threshold=1.5,
        strong_threshold=1.0,
        weight=0.8,
        tags=["asset_value"],
    ),
    # ── V05–V10: Expanded institutional value signals ───────────────
    AlphaSignalDefinition(
        id="value.shareholder_yield",
        name="High Shareholder Yield",
        category=SignalCategory.VALUE,
        description="Combined dividend + buyback + debt paydown yield exceeds threshold (Meb Faber strategy)",
        feature_path="fundamental.shareholder_yield",
        direction=SignalDirection.ABOVE,
        threshold=0.03,
        strong_threshold=0.06,
        weight=1.1,
        tags=["total_return", "capital_allocation"],
    ),
    AlphaSignalDefinition(
        id="value.peg_low",
        name="Low PEG Ratio",
        category=SignalCategory.VALUE,
        description="P/E adjusted for growth rate below 1.0 suggests undervalued relative to growth (Peter Lynch)",
        feature_path="fundamental.peg_ratio",
        direction=SignalDirection.BELOW,
        threshold=1.2,
        strong_threshold=0.8,
        weight=1.0,
        tags=["growth_at_reasonable_price"],
    ),
    AlphaSignalDefinition(
        id="value.ev_revenue_low",
        name="Low EV/Revenue",
        category=SignalCategory.VALUE,
        description="Enterprise value to revenue below sector norm — useful for pre-profit and SaaS companies",
        feature_path="fundamental.ev_revenue",
        direction=SignalDirection.BELOW,
        threshold=3.0,
        strong_threshold=1.0,
        weight=0.8,
        tags=["revenue_based_value"],
    ),
    AlphaSignalDefinition(
        id="value.div_yield_vs_hist",
        name="Dividend Yield vs Historical Average",
        category=SignalCategory.VALUE,
        description="Current dividend yield exceeds 5-year average, signalling price dislocation (Dogs of the Dow)",
        feature_path="fundamental.dividend_yield",
        direction=SignalDirection.ABOVE,
        threshold=0.03,
        strong_threshold=0.05,
        weight=0.9,
        tags=["income", "mean_reversion"],
    ),
    AlphaSignalDefinition(
        id="value.ebit_ev_high",
        name="High EBIT/EV (Greenblatt)",
        category=SignalCategory.VALUE,
        description="EBIT yield on enterprise value — Greenblatt Magic Formula first factor, capital-structure neutral",
        feature_path="fundamental.ebit_ev",
        direction=SignalDirection.ABOVE,
        threshold=0.08,
        strong_threshold=0.12,
        weight=1.1,
        tags=["magic_formula", "operating_yield"],
    ),
    AlphaSignalDefinition(
        id="value.ncav_deep",
        name="Net Current Asset Value Deep Value",
        category=SignalCategory.VALUE,
        description="Market cap below net current assets (Ben Graham net-net) — extreme deep value liquidation discount",
        feature_path="fundamental.ncav_ratio",
        direction=SignalDirection.ABOVE,
        threshold=0.7,
        strong_threshold=1.0,
        weight=0.7,
        tags=["deep_value", "graham"],
    ),
]

# Auto-register
registry.register_many(VALUE_SIGNALS)
