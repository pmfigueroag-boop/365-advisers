"""
src/contracts/features.py
──────────────────────────────────────────────────────────────────────────────
Layer 2 output contracts — normalised feature sets produced by the
Feature / Indicator Layer and consumed by the Analysis Engines.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ─── Fundamental Features ─────────────────────────────────────────────────────

class FundamentalFeatureSet(BaseModel):
    """
    Normalised fundamental features extracted from FinancialStatements.
    All values are floats or None (never raw strings like "DATA_INCOMPLETE").
    """
    ticker: str

    # Profitability
    roic: float | None = None
    roe: float | None = None
    gross_margin: float | None = None
    ebit_margin: float | None = None
    net_margin: float | None = None

    # Cash Flow
    fcf_yield: float | None = None

    # Leverage
    debt_to_equity: float | None = None
    debt_to_ebitda: float | None = None  # derived if possible
    current_ratio: float | None = None
    quick_ratio: float | None = None

    # Growth
    revenue_growth_yoy: float | None = None
    earnings_growth_yoy: float | None = None

    # Valuation
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ev_ebitda: float | None = None

    # Quality
    dividend_yield: float = 0.0
    payout_ratio: float = 0.0
    beta: float | None = None

    # Margin Trend (direction)
    margin_trend: float | None = None  # positive = expanding, negative = contracting

    # Earnings Stability proxy
    earnings_stability: float | None = None

    # C4: Sector-relative valuation adjustment factor (1.0 = no adjustment)
    sector_pe_adjustment: float = 1.0

    # C6: Fundamental momentum / acceleration
    revenue_acceleration: float | None = None   # QoQ change in revenue growth rate
    margin_expansion_rate: float | None = None   # Same as margin_trend but expressed as rate

    # Context
    sector: str = ""
    industry: str = ""
    market_cap: float | None = None
    name: str = ""
    description: str = ""


# ─── Technical Features ───────────────────────────────────────────────────────

class TechnicalFeatureSet(BaseModel):
    """
    Normalised technical features extracted from PriceHistory + MarketMetrics.
    All indicator values are floats ready for consumption by the Technical Engine.
    """
    ticker: str
    current_price: float = 0.0

    # Moving Averages
    sma_50: float = 0.0
    sma_200: float = 0.0
    ema_20: float = 0.0

    # Momentum
    rsi: float = 50.0
    stoch_k: float = 50.0
    stoch_d: float = 50.0

    # MACD
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0

    # Volatility
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    bb_basis: float = 0.0
    atr: float = 0.0

    # Volume
    volume: float = 0.0
    obv: float = 0.0
    volume_avg_20: float = 0.0  # 20-period average volume

    # OHLCV bars (for structure analysis)
    ohlcv: list[dict] = Field(default_factory=list)

    # Regime detection (ADX + Directional Indicators)
    adx: float = 20.0
    plus_di: float = 20.0
    minus_di: float = 20.0

    # TradingView consensus
    tv_recommendation: str = "UNKNOWN"

    # Derived risk features
    sma50_below_sma200: float = 0.0  # (sma_50 / sma_200) - 1 ; negative = death cross

    # C7: Price cycle positioning
    pct_from_52w_high: float | None = None   # negative = below high
    mean_reversion_z: float | None = None     # z-score vs 1yr mean price

    @property
    def _compute_sma50_below_sma200(self) -> float:
        if self.sma_200 > 0:
            return (self.sma_50 / self.sma_200) - 1.0
        return 0.0

    def model_post_init(self, __context) -> None:
        """Compute derived features after initialization."""
        if self.sma_200 > 0 and self.sma50_below_sma200 == 0.0:
            self.sma50_below_sma200 = round((self.sma_50 / self.sma_200) - 1.0, 6)
