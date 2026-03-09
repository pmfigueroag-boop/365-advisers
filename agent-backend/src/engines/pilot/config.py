"""
src/engines/pilot/config.py
─────────────────────────────────────────────────────────────────────────────
Centralized configuration for the 365 Advisers Pilot Deployment.

All parameters from the pilot design document are encoded here as
typed constants and default portfolio configurations.
"""

from __future__ import annotations

from .models import (
    EntryExitCriteria,
    PilotPortfolioConfig,
    PortfolioType,
)


# ─── General Parameters ────────────────────────────────────────────────────

PILOT_DURATION_WEEKS: int = 12
PILOT_UNIVERSE: str = "sp500"
PILOT_INITIAL_CAPITAL: float = 1_000_000.0
PILOT_ANALYSIS_FREQUENCY: str = "daily"
PILOT_REBALANCE_FREQUENCY: str = "weekly"
PILOT_REBALANCE_DAY: str = "friday"

# Pilot universe — representative S&P 500 tickers for fast daily cycles
# Covers: Tech (AAPL, MSFT, GOOGL, NVDA), Finance (JPM, V),
#         Healthcare (JNJ), Consumer (AMZN, PG), Energy (XOM)
PILOT_TICKERS: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "JPM", "JNJ", "PG", "XOM", "V",
]

# Strategy templates for the pilot blend
PILOT_STRATEGY_CONFIGS: list[dict] = [
    {
        "name": "Momentum Quality",
        "strategy_id": "momentum_quality",
        "required_categories": ["momentum", "quality"],
        "composition_logic": "AND",
        "min_strength": 0.5,
        "min_confidence": "medium",
        "min_case": 60.0,
        "min_bq": 6.0,
        "min_uos": 6.5,
        "max_freshness": "stale",
    },
    {
        "name": "Value Contrarian",
        "strategy_id": "value_contrarian",
        "required_categories": ["value"],
        "composition_logic": "OR",
        "min_strength": 0.3,
        "min_confidence": "low",
        "min_case": 55.0,
        "min_bq": 5.5,
        "min_uos": 6.0,
        "max_freshness": "diluted",
    },
    {
        "name": "Low Volatility",
        "strategy_id": "low_volatility",
        "required_categories": ["volatility", "quality"],
        "composition_logic": "AND",
        "min_strength": 0.3,
        "min_confidence": "medium",
        "min_case": 50.0,
        "min_bq": 6.0,
        "min_uos": 6.0,
        "max_freshness": "stale",
    },
]


# ─── Alert Thresholds ──────────────────────────────────────────────────────

class AlertThresholds:
    """Threshold values that trigger pilot alerts."""

    # Signal degradation: hit rate (rolling 20d) for a full category
    SIGNAL_HR_WARNING: float = 0.45            # Below 45% → WARNING

    # Strategy drawdown
    STRATEGY_DD_WARNING: float = 0.10          # 10% drawdown → WARNING
    STRATEGY_DD_CRITICAL: float = 0.15         # 15% drawdown → CRITICAL (auto-pause)

    # Portfolio volatility (annualised, rolling 5d)
    PORTFOLIO_VOL_WARNING: float = 0.25        # 25% → WARNING
    PORTFOLIO_VOL_CRITICAL: float = 0.35       # 35% → CRITICAL (emergency de-risk)

    # Data freshness
    DATA_STALENESS_HOURS: float = 2.0          # > 2h post-close → WARNING

    # CASE score collapse
    CASE_EXPIRED_RATIO: float = 0.30           # ≥ 30% signals expired → WARNING

    # Intra-portfolio correlation
    CORRELATION_WARNING: float = 0.70          # > 0.7 rolling 20d → WARNING


# ─── Metric Targets (Go / No-Go) ───────────────────────────────────────────

class MetricTargets:
    """
    Target values for the 6 quantitative Go/No-Go criteria.
    The pilot recommends GO if ≥ 4 of 6 are met.
    """

    # 1. Signal Hit Rate (aggregate, 20d forward)
    SIGNAL_HIT_RATE: float = 0.53

    # 2. Research Portfolio Alpha vs benchmark
    RESEARCH_ALPHA: float = 0.0        # > 0% (positive alpha)

    # 3. Strategy Portfolio Sharpe
    STRATEGY_SHARPE: float = 0.8

    # 4. Max Drawdown (all portfolios)
    MAX_DRAWDOWN: float = 0.20         # < 20%

    # 5. Strategy Quality Score (avg)
    STRATEGY_QUALITY: float = 60.0     # > 60 (out of 100)

    # 6. System Uptime
    SYSTEM_UPTIME: float = 0.99        # > 99%

    # Minimum criteria passed for GO
    MIN_CRITERIA_FOR_GO: int = 4
    TOTAL_CRITERIA: int = 6


# ─── Default Portfolio Configurations ───────────────────────────────────────


def get_research_portfolio_config() -> PilotPortfolioConfig:
    """Research Portfolio — driven by signals and ideas."""
    return PilotPortfolioConfig(
        portfolio_type=PortfolioType.RESEARCH,
        name="Pilot Research Portfolio",
        sizing_method="vol_parity",
        max_positions=20,
        max_single_position_pct=0.10,
        max_sector_exposure_pct=0.25,
        rebalance_frequency="weekly",
        initial_capital=PILOT_INITIAL_CAPITAL,
        entry_exit=EntryExitCriteria(
            min_case_score=65.0,
            min_uos=7.0,
            min_active_signals=3,
            exit_case_score=40.0,
            trailing_stop_pct=0.12,
            time_stop_days=30,
        ),
        regime_bear_action="reduce_50",
    )


def get_strategy_portfolio_config() -> PilotPortfolioConfig:
    """Strategy Portfolio — blend of 3 strategies from the Strategy Lab."""
    return PilotPortfolioConfig(
        portfolio_type=PortfolioType.STRATEGY,
        name="Pilot Strategy Portfolio",
        sizing_method="vol_parity",
        max_positions=30,
        max_single_position_pct=0.10,
        max_sector_exposure_pct=0.25,
        rebalance_frequency="weekly",
        initial_capital=PILOT_INITIAL_CAPITAL,
        strategy_ids=[
            "momentum_quality",
            "value_contrarian",
            "low_volatility",
        ],
        blend_method="risk_parity",
        regime_bear_action="no_new_entries",
    )


def get_benchmark_portfolio_config() -> PilotPortfolioConfig:
    """Benchmark Portfolio — static 70/30 SPY/QQQ."""
    return PilotPortfolioConfig(
        portfolio_type=PortfolioType.BENCHMARK,
        name="Pilot Benchmark Portfolio",
        sizing_method="equal_weight",
        max_positions=2,
        rebalance_frequency="monthly",
        initial_capital=PILOT_INITIAL_CAPITAL,
        benchmark_weights={
            "SPY": 0.70,
            "QQQ": 0.30,
        },
    )


def get_all_portfolio_configs() -> list[PilotPortfolioConfig]:
    """Return all three default pilot portfolio configurations."""
    return [
        get_research_portfolio_config(),
        get_strategy_portfolio_config(),
        get_benchmark_portfolio_config(),
    ]
