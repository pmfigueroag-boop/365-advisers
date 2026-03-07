"""
src/engines/benchmark_factor/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Benchmark & Factor Neutral Evaluation Model.

Defines configuration, per-benchmark results, factor exposure profiles,
signal profiles, and the complete evaluation report.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ─── Enumerations ────────────────────────────────────────────────────────────

class AlphaSource(str, Enum):
    """Classification of where a signal's return comes from."""
    PURE_ALPHA = "pure_alpha"       # Significant α + low R²
    MIXED = "mixed"                 # Significant α + moderate/high R²
    FACTOR_BETA = "factor_beta"     # No significant α


# ─── Sector Mapping ──────────────────────────────────────────────────────────

# Top 80 S&P 500 tickers → sector ETF
SECTOR_MAP: dict[str, str] = {
    # Technology (XLK)
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "XLK", "AVGO": "XLK",
    "CSCO": "XLK", "ADBE": "XLK", "CRM": "XLK", "ORCL": "XLK",
    "ACN": "XLK", "INTC": "XLK", "AMD": "XLK", "TXN": "XLK",
    "QCOM": "XLK", "IBM": "XLK", "INTU": "XLK", "AMAT": "XLK",
    # Communication Services (XLC)
    "GOOGL": "XLC", "GOOG": "XLC", "META": "XLC", "NFLX": "XLC",
    "DIS": "XLC", "TMUS": "XLC", "VZ": "XLC", "T": "XLC",
    # Consumer Discretionary (XLY)
    "AMZN": "XLY", "TSLA": "XLY", "HD": "XLY", "NKE": "XLY",
    "MCD": "XLY", "SBUX": "XLY", "LOW": "XLY", "TJX": "XLY",
    # Healthcare (XLV)
    "UNH": "XLV", "JNJ": "XLV", "LLY": "XLV", "PFE": "XLV",
    "ABBV": "XLV", "MRK": "XLV", "TMO": "XLV", "ABT": "XLV",
    "DHR": "XLV", "BMY": "XLV", "AMGN": "XLV", "GILD": "XLV",
    # Financials (XLF)
    "JPM": "XLF", "BAC": "XLF", "WFC": "XLF", "GS": "XLF",
    "MS": "XLF", "BLK": "XLF", "SCHW": "XLF", "C": "XLF",
    "AXP": "XLF", "BRK-B": "XLF", "V": "XLF", "MA": "XLF",
    # Energy (XLE)
    "XOM": "XLE", "CVX": "XLE", "COP": "XLE", "SLB": "XLE",
    "EOG": "XLE", "MPC": "XLE", "PSX": "XLE", "VLO": "XLE",
    # Consumer Staples (XLP)
    "PG": "XLP", "KO": "XLP", "PEP": "XLP", "COST": "XLP",
    "WMT": "XLP", "PM": "XLP", "MO": "XLP", "CL": "XLP",
    # Industrials (XLI)
    "CAT": "XLI", "RTX": "XLI", "HON": "XLI", "UPS": "XLI",
    "BA": "XLI", "DE": "XLI", "GE": "XLI", "LMT": "XLI",
    # Utilities (XLU)
    "NEE": "XLU", "DUK": "XLU", "SO": "XLU", "D": "XLU",
    # Real Estate (XLRE)
    "PLD": "XLRE", "AMT": "XLRE", "EQIX": "XLRE", "SPG": "XLRE",
    # Materials (XLB)
    "LIN": "XLB", "APD": "XLB", "SHW": "XLB", "ECL": "XLB",
}


# ─── Configuration ───────────────────────────────────────────────────────────

class FactorTickers(BaseModel):
    """ETF proxies for constructing factor return series."""
    market: str = "SPY"
    small_cap: str = "IWM"
    value: str = "IWD"
    growth: str = "IWF"
    momentum: str = "MTUM"


class BenchmarkConfig(BaseModel):
    """Configuration for benchmark & factor evaluation."""
    market_benchmark: str = Field("SPY", description="Primary market benchmark")
    additional_benchmarks: list[str] = Field(
        default_factory=lambda: ["QQQ", "IWM"],
        description="Extra index benchmarks to compare against",
    )
    sector_benchmarks: dict[str, str] = Field(
        default_factory=lambda: dict(SECTOR_MAP),
        description="Ticker → sector ETF mapping",
    )
    factor_tickers: FactorTickers = Field(
        default_factory=FactorTickers,
        description="ETF proxies for factor construction",
    )
    enable_factor_regression: bool = Field(
        True, description="Run 4-factor OLS regression",
    )
    min_observations: int = Field(
        10, ge=3, description="Minimum events for regression",
    )
    forward_window: int = Field(
        20, description="Primary forward window for factor analysis",
    )


# ─── Per-Benchmark Result ───────────────────────────────────────────────────

class BenchmarkResult(BaseModel):
    """Signal performance vs a single benchmark."""
    benchmark_ticker: str
    benchmark_name: str = ""
    excess_return: dict[int, float] = Field(
        default_factory=dict,
        description="{window: mean excess return}",
    )
    information_ratio: dict[int, float] = Field(
        default_factory=dict,
        description="{window: annualised IR}",
    )
    tracking_error: dict[int, float] = Field(
        default_factory=dict,
        description="{window: annualised TE}",
    )
    hit_rate_vs_bench: dict[int, float] = Field(
        default_factory=dict,
        description="{window: % events beating benchmark}",
    )


# ─── Factor Exposure ────────────────────────────────────────────────────────

class FactorExposure(BaseModel):
    """Factor regression results for a signal."""
    factor_alpha: float = 0.0
    alpha_t_stat: float = 0.0
    alpha_significant: bool = False
    beta_market: float = 0.0
    beta_size: float = 0.0
    beta_value: float = 0.0
    beta_momentum: float = 0.0
    r_squared: float = 0.0
    factor_neutrality: float = 1.0
    n_observations: int = 0
    forward_window: int = 20


# ─── Signal Profile ─────────────────────────────────────────────────────────

class SignalBenchmarkProfile(BaseModel):
    """Complete benchmark & factor profile for one signal."""
    signal_id: str
    signal_name: str = ""
    total_events: int = 0
    benchmark_results: list[BenchmarkResult] = Field(default_factory=list)
    sector_result: BenchmarkResult | None = None
    factor_exposure: FactorExposure | None = None
    alpha_source: AlphaSource = AlphaSource.FACTOR_BETA


# ─── Complete Report ─────────────────────────────────────────────────────────

class BenchmarkFactorReport(BaseModel):
    """Full output of the benchmark & factor evaluation."""
    config: BenchmarkConfig
    signal_profiles: list[SignalBenchmarkProfile] = Field(default_factory=list)
    pure_alpha_signals: list[str] = Field(
        default_factory=list,
        description="Signals with genuine factor-independent alpha",
    )
    factor_dependent_signals: list[str] = Field(
        default_factory=list,
        description="Signals whose returns are explained by factors",
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
