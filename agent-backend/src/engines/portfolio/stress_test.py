"""
src/engines/portfolio/stress_test.py
--------------------------------------------------------------------------
Portfolio Stress Testing — historical scenario replay and custom shocks.

Scenarios
~~~~~~~~~
- COVID crash (Feb–Mar 2020): ~-34% drawdown in 23 days
- 2022 Rate Shock:  ~-25% over 9 months
- 2008 GFC:         ~-57% over 17 months
- Custom:           user-defined factor shocks

Method
~~~~~~
1. Takes portfolio weights + factor exposures
2. Applies scenario shocks to each factor
3. Computes estimated portfolio impact: Δ_portfolio = Σ(weight × beta × shock)
4. Reports per-position and portfolio-level impact

Usage::

    stress = StressTestEngine()
    result = stress.run(
        weights={"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4},
        scenarios=["covid", "gfc_2008"],
    )
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.portfolio.stress_test")


# ── Predefined Scenarios ─────────────────────────────────────────────────────

class ScenarioShock(BaseModel):
    """A predefined market shock scenario."""
    name: str
    description: str = ""
    market_return: float = 0.0
    duration_days: int = 0
    factor_shocks: dict[str, float] = Field(
        default_factory=dict,
        description="Factor → shock magnitude (e.g., 'equity': -0.34)",
    )


# Historical scenarios
SCENARIOS: dict[str, ScenarioShock] = {
    "covid": ScenarioShock(
        name="COVID Crash",
        description="Feb-Mar 2020: rapid 34% decline in 23 trading days",
        market_return=-0.34,
        duration_days=23,
        factor_shocks={
            "equity": -0.34,
            "small_cap": -0.40,
            "value": -0.28,
            "momentum": -0.15,
            "quality": -0.10,
            "volatility": 0.50,
        },
    ),
    "gfc_2008": ScenarioShock(
        name="2008 Global Financial Crisis",
        description="Oct 2007 - Mar 2009: ~57% decline over 17 months",
        market_return=-0.57,
        duration_days=354,
        factor_shocks={
            "equity": -0.57,
            "small_cap": -0.60,
            "value": -0.55,
            "momentum": 0.10,
            "quality": -0.20,
            "volatility": 0.80,
        },
    ),
    "rate_shock_2022": ScenarioShock(
        name="2022 Rate Shock",
        description="Jan-Oct 2022: ~25% decline as rates surged",
        market_return=-0.25,
        duration_days=200,
        factor_shocks={
            "equity": -0.25,
            "small_cap": -0.30,
            "value": 0.05,
            "momentum": -0.20,
            "quality": -0.08,
            "volatility": 0.35,
        },
    ),
    "rates_up_200bp": ScenarioShock(
        name="Interest Rates +200bp",
        description="Hypothetical: rates rise 200bps over 3 months",
        market_return=-0.12,
        duration_days=63,
        factor_shocks={
            "equity": -0.12,
            "small_cap": -0.15,
            "value": 0.03,
            "momentum": -0.08,
            "quality": -0.05,
            "volatility": 0.20,
        },
    ),
    "oil_crash": ScenarioShock(
        name="Oil Price -40%",
        description="Hypothetical: oil drops 40%",
        market_return=-0.08,
        duration_days=42,
        factor_shocks={
            "equity": -0.08,
            "small_cap": -0.10,
            "value": -0.12,
            "momentum": -0.05,
            "quality": -0.03,
            "volatility": 0.15,
        },
    ),
}


# ── Contracts ────────────────────────────────────────────────────────────────

class PositionImpact(BaseModel):
    """Impact of a stress scenario on a single position."""
    ticker: str
    weight: float
    beta: float = 1.0
    estimated_loss: float = 0.0
    contribution_to_portfolio_loss: float = 0.0


class ScenarioResult(BaseModel):
    """Result of one stress scenario."""
    scenario: ScenarioShock
    portfolio_impact: float = Field(
        0.0, description="Estimated portfolio-level return under scenario",
    )
    portfolio_loss_pct: float = Field(
        0.0, description="Portfolio loss as percentage",
    )
    position_impacts: list[PositionImpact] = Field(default_factory=list)
    worst_position: str = ""
    worst_position_loss: float = 0.0


class StressTestReport(BaseModel):
    """Full stress test output."""
    scenario_results: list[ScenarioResult] = Field(default_factory=list)
    total_scenarios: int = 0
    worst_case_scenario: str = ""
    worst_case_loss: float = 0.0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

class StressTestEngine:
    """
    Portfolio stress testing engine.

    Usage::

        engine = StressTestEngine()
        report = engine.run(
            weights={"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4},
            scenarios=["covid", "gfc_2008"],
        )
    """

    def __init__(
        self,
        betas: dict[str, float] | None = None,
        sector_map: dict[str, str] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        betas : dict[str, float] | None
            Per-ticker market beta. Default: 1.0 for all.
        sector_map : dict[str, str] | None
            Ticker → sector mapping for sector-aware shocks.
        """
        self.betas = betas or {}
        self.sector_map = sector_map or {}

    def run(
        self,
        weights: dict[str, float],
        scenarios: list[str] | None = None,
        custom_scenarios: list[ScenarioShock] | None = None,
    ) -> StressTestReport:
        """
        Run stress tests on portfolio.

        Parameters
        ----------
        weights : dict[str, float]
            Portfolio weights {ticker: weight}.
        scenarios : list[str] | None
            Predefined scenario names (from SCENARIOS dict).
        custom_scenarios : list[ScenarioShock] | None
            Custom user-defined scenarios.
        """
        if not weights:
            return StressTestReport()

        # Collect scenarios to run
        scen_list: list[ScenarioShock] = []

        if scenarios:
            for name in scenarios:
                if name in SCENARIOS:
                    scen_list.append(SCENARIOS[name])
                else:
                    logger.warning("STRESS: Unknown scenario '%s', skipping", name)

        if custom_scenarios:
            scen_list.extend(custom_scenarios)

        if not scen_list:
            # Default: run all predefined
            scen_list = list(SCENARIOS.values())

        results: list[ScenarioResult] = []

        for scenario in scen_list:
            result = self._evaluate_scenario(weights, scenario)
            results.append(result)

        # Find worst case
        worst = min(results, key=lambda r: r.portfolio_impact) if results else None

        return StressTestReport(
            scenario_results=results,
            total_scenarios=len(results),
            worst_case_scenario=worst.scenario.name if worst else "",
            worst_case_loss=round(worst.portfolio_impact, 6) if worst else 0.0,
        )

    def _evaluate_scenario(
        self,
        weights: dict[str, float],
        scenario: ScenarioShock,
    ) -> ScenarioResult:
        """Evaluate one scenario's impact on the portfolio."""
        impacts: list[PositionImpact] = []
        portfolio_impact = 0.0

        for ticker, weight in weights.items():
            if weight <= 0.001:
                continue

            beta = self.betas.get(ticker, 1.0)

            # Estimated position loss = weight × beta × market_return
            position_loss = weight * beta * scenario.market_return
            portfolio_impact += position_loss

            impacts.append(PositionImpact(
                ticker=ticker,
                weight=round(weight, 4),
                beta=round(beta, 4),
                estimated_loss=round(position_loss, 6),
                contribution_to_portfolio_loss=round(position_loss, 6),
            ))

        # Sort by loss (worst first)
        impacts.sort(key=lambda p: p.estimated_loss)
        worst_pos = impacts[0] if impacts else None

        return ScenarioResult(
            scenario=scenario,
            portfolio_impact=round(portfolio_impact, 6),
            portfolio_loss_pct=round(portfolio_impact * 100, 4),
            position_impacts=impacts,
            worst_position=worst_pos.ticker if worst_pos else "",
            worst_position_loss=worst_pos.estimated_loss if worst_pos else 0.0,
        )

    @staticmethod
    def list_scenarios() -> dict[str, str]:
        """List available predefined scenarios."""
        return {name: s.description for name, s in SCENARIOS.items()}
