"""
src/engines/risk/scenario_stress_engine.py
--------------------------------------------------------------------------
Enhanced Scenario Stress Testing Engine.

Extends the basic StressTester with:
  - Sector-level impact aggregation
  - Correlation-adjusted portfolio impact
  - Parametric scenario generation (vol + correlation shock)
  - Conditional tail expectations (what-if worst N% case)

Usage::

    engine = ScenarioStressEngine()
    report = engine.run_suite(portfolio_weights, sectors)
"""

from __future__ import annotations

import logging
import math

from pydantic import BaseModel, Field

from src.engines.risk.models import StressScenario, StressResult

logger = logging.getLogger("365advisers.risk.scenario_stress")


# ── Contracts ────────────────────────────────────────────────────────────────

class SectorImpact(BaseModel):
    """Per-sector impact from a stress scenario."""
    sector: str
    weight: float = 0.0
    shock_pct: float = 0.0
    impact_pct: float = 0.0
    tickers: list[str] = Field(default_factory=list)


class EnhancedStressResult(BaseModel):
    """Enhanced stress result with sector breakdown."""
    scenario_name: str
    description: str = ""
    portfolio_impact_pct: float = 0.0
    portfolio_impact_amount: float = 0.0
    worst_position: str = ""
    worst_position_impact: float = 0.0
    sector_impacts: list[SectorImpact] = Field(default_factory=list)
    correlation_adjusted_impact: float = 0.0
    tail_loss_pct: float = 0.0  # Expected loss in worst case
    survives: bool = True  # Portfolio survives scenario


class StressSuiteReport(BaseModel):
    """Full suite of stress test results."""
    results: list[EnhancedStressResult] = Field(default_factory=list)
    worst_scenario: str = ""
    max_drawdown_pct: float = 0.0
    scenarios_survived: int = 0
    total_scenarios: int = 0
    risk_score: float = 0.0  # 0-100, higher = more resilient


# ── Built-in Scenarios ──────────────────────────────────────────────────────

ENHANCED_SCENARIOS = [
    StressScenario(
        name="2008_gfc", description="Global Financial Crisis (Sep-Nov 2008)",
        shocks={"SPY": -0.38, "QQQ": -0.42, "IWM": -0.40, "EFA": -0.45,
                "TLT": 0.20, "GLD": 0.05, "XLF": -0.55, "XLK": -0.40,
                "XLV": -0.25, "XLE": -0.45, "XLU": -0.20},
    ),
    StressScenario(
        name="covid_crash", description="COVID-19 Market Crash (Feb-Mar 2020)",
        shocks={"SPY": -0.34, "QQQ": -0.28, "IWM": -0.42, "EFA": -0.35,
                "TLT": 0.22, "GLD": 0.03, "XLF": -0.38, "XLK": -0.25,
                "XLV": -0.15, "XLE": -0.55, "XLU": -0.20},
    ),
    StressScenario(
        name="rate_shock_300bp", description="Aggressive Rate Hike (+300bp)",
        shocks={"SPY": -0.15, "QQQ": -0.25, "TLT": -0.20, "IEF": -0.10,
                "GLD": -0.05, "XLF": 0.05, "XLU": -0.18, "XLK": -0.22},
    ),
    StressScenario(
        name="sector_rotation", description="Growth→Value Rotation",
        shocks={"QQQ": -0.20, "XLK": -0.18, "XLF": 0.10, "XLE": 0.12,
                "XLI": 0.08, "SPY": -0.05, "IWM": 0.05},
    ),
    StressScenario(
        name="stagflation", description="Stagflation Scenario",
        shocks={"SPY": -0.20, "QQQ": -0.25, "TLT": -0.15, "GLD": 0.15,
                "XLE": 0.08, "XLU": -0.10, "XLF": -0.15, "IWM": -0.25},
    ),
    StressScenario(
        name="liquidity_crisis", description="Liquidity Crisis / Flash Crash",
        shocks={"SPY": -0.12, "QQQ": -0.15, "IWM": -0.20, "EFA": -0.14,
                "HYG": -0.08, "TLT": 0.10, "GLD": 0.06, "XLF": -0.18},
    ),
]


# ── Engine ───────────────────────────────────────────────────────────────────

class ScenarioStressEngine:
    """Enhanced scenario stress testing with sector decomposition."""

    def __init__(self, max_acceptable_drawdown: float = 0.30) -> None:
        self.max_acceptable_drawdown = max_acceptable_drawdown

    def run_suite(
        self,
        portfolio_weights: dict[str, float],
        ticker_sectors: dict[str, str] | None = None,
        portfolio_value: float = 1_000_000.0,
        scenarios: list[StressScenario] | None = None,
    ) -> StressSuiteReport:
        """
        Run full stress test suite against portfolio.

        Parameters
        ----------
        portfolio_weights : dict[str, float]
            Ticker → weight.
        ticker_sectors : dict[str, str] | None
            Ticker → sector mapping for sector-level analysis.
        portfolio_value : float
            Portfolio value for dollar impact.
        scenarios : list[StressScenario] | None
            Custom scenarios (default: ENHANCED_SCENARIOS).
        """
        scenarios = scenarios or ENHANCED_SCENARIOS
        sectors = ticker_sectors or {}
        results: list[EnhancedStressResult] = []

        for scenario in scenarios:
            result = self._run_scenario(
                portfolio_weights, scenario, sectors, portfolio_value,
            )
            results.append(result)

        # Aggregate
        worst = min(results, key=lambda r: r.portfolio_impact_pct) if results else None
        n_survived = sum(1 for r in results if r.survives)
        max_dd = abs(min(r.portfolio_impact_pct for r in results)) if results else 0

        # Risk resilience score: 100 = survives everything, 0 = fails everything
        risk_score = (n_survived / len(results) * 60 + max(0, 30 - max_dd) + 10) if results else 0
        risk_score = min(100, max(0, risk_score))

        return StressSuiteReport(
            results=results,
            worst_scenario=worst.scenario_name if worst else "",
            max_drawdown_pct=round(max_dd, 2),
            scenarios_survived=n_survived,
            total_scenarios=len(results),
            risk_score=round(risk_score, 1),
        )

    def _run_scenario(
        self,
        portfolio_weights: dict[str, float],
        scenario: StressScenario,
        ticker_sectors: dict[str, str],
        portfolio_value: float,
    ) -> EnhancedStressResult:
        """Run a single stress scenario."""
        total_impact = 0.0
        worst_ticker = ""
        worst_impact = 0.0
        sector_data: dict[str, dict] = {}

        for ticker, weight in portfolio_weights.items():
            shock = scenario.shocks.get(ticker, 0.0)
            impact = weight * shock
            total_impact += impact

            if abs(impact) > abs(worst_impact):
                worst_impact = impact
                worst_ticker = ticker

            # Sector aggregation
            sector = ticker_sectors.get(ticker, "Unknown")
            if sector not in sector_data:
                sector_data[sector] = {"weight": 0, "impact": 0, "tickers": []}
            sector_data[sector]["weight"] += weight
            sector_data[sector]["impact"] += impact
            sector_data[sector]["tickers"].append(ticker)

        # Correlation adjustment: diversified portfolio loses less
        n_positions = len(portfolio_weights)
        diversification_benefit = 1.0 - min(0.15, 0.03 * math.sqrt(n_positions))
        corr_adjusted = total_impact * diversification_benefit

        # Tail loss: 1.5x scenario at 99th percentile
        tail_loss = total_impact * 1.5

        sector_impacts = [
            SectorImpact(
                sector=s,
                weight=round(d["weight"], 4),
                shock_pct=round(d["impact"] / d["weight"] * 100, 2) if d["weight"] > 0 else 0,
                impact_pct=round(d["impact"] * 100, 2),
                tickers=d["tickers"],
            )
            for s, d in sorted(sector_data.items(), key=lambda x: x[1]["impact"])
        ]

        survives = abs(total_impact) < self.max_acceptable_drawdown

        return EnhancedStressResult(
            scenario_name=scenario.name,
            description=scenario.description,
            portfolio_impact_pct=round(total_impact * 100, 2),
            portfolio_impact_amount=round(total_impact * portfolio_value, 2),
            worst_position=worst_ticker,
            worst_position_impact=round(worst_impact * 100, 2),
            sector_impacts=sector_impacts,
            correlation_adjusted_impact=round(corr_adjusted * 100, 2),
            tail_loss_pct=round(tail_loss * 100, 2),
            survives=survives,
        )

    @classmethod
    def parametric_scenario(
        cls,
        name: str,
        market_shock: float,
        vol_multiplier: float = 1.0,
        sector_shocks: dict[str, float] | None = None,
    ) -> StressScenario:
        """
        Generate parametric scenario from market-level shock.

        Parameters
        ----------
        market_shock : float
            Base market shock (e.g. -0.20 for 20% decline).
        vol_multiplier : float
            Scale factor for volatility (1.0 = normal).
        sector_shocks : dict | None
            Override sector-specific shocks.
        """
        base_betas = {
            "SPY": 1.0, "QQQ": 1.3, "IWM": 1.2, "EFA": 0.95,
            "TLT": -0.3, "GLD": -0.1, "XLF": 1.1, "XLK": 1.3,
            "XLV": 0.7, "XLE": 1.0, "XLU": 0.5,
        }
        shocks = {}
        for ticker, beta in base_betas.items():
            shocks[ticker] = round(market_shock * beta * vol_multiplier, 4)

        if sector_shocks:
            shocks.update(sector_shocks)

        return StressScenario(
            name=name,
            description=f"Parametric: {market_shock:.0%} market, {vol_multiplier:.1f}x vol",
            shocks=shocks,
        )
