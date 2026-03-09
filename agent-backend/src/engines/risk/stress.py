"""src/engines/risk/stress.py — Stress testing."""
from __future__ import annotations
import logging
from src.engines.risk.models import StressScenario, StressResult

logger = logging.getLogger("365advisers.risk.stress")

# Built-in scenarios
BUILTIN_SCENARIOS = [
    StressScenario(
        name="2008_financial_crisis", description="Global Financial Crisis (Sep-Nov 2008)",
        shocks={"SPY": -0.38, "QQQ": -0.42, "IWM": -0.40, "EFA": -0.45, "TLT": 0.20, "GLD": 0.05},
    ),
    StressScenario(
        name="covid_crash", description="COVID-19 Market Crash (Feb-Mar 2020)",
        shocks={"SPY": -0.34, "QQQ": -0.28, "IWM": -0.42, "EFA": -0.35, "TLT": 0.22, "GLD": 0.03},
    ),
    StressScenario(
        name="rate_shock", description="Aggressive Rate Hike Scenario",
        shocks={"SPY": -0.15, "QQQ": -0.25, "TLT": -0.20, "IEF": -0.10, "GLD": -0.05, "XLF": 0.05},
    ),
    StressScenario(
        name="tech_selloff", description="Technology sector selloff",
        shocks={"QQQ": -0.30, "SPY": -0.12, "AAPL": -0.25, "MSFT": -0.25, "GOOGL": -0.30, "XLK": -0.28},
    ),
]


class StressTester:
    """Apply stress scenarios to portfolio weights."""

    @classmethod
    def apply_scenario(
        cls, portfolio_weights: dict[str, float], scenario: StressScenario,
        portfolio_value: float = 1_000_000.0,
    ) -> StressResult:
        """Apply a stress scenario to portfolio and compute impact."""
        total_impact = 0.0
        worst_ticker = ""
        worst_impact = 0.0

        for ticker, weight in portfolio_weights.items():
            shock = scenario.shocks.get(ticker, 0.0)
            impact = weight * shock
            total_impact += impact
            if abs(impact) > abs(worst_impact):
                worst_impact = impact
                worst_ticker = ticker

        return StressResult(
            scenario_name=scenario.name,
            portfolio_impact_pct=round(total_impact * 100, 2),
            portfolio_impact_amount=round(total_impact * portfolio_value, 2),
            worst_position=worst_ticker,
            worst_position_impact=round(worst_impact * 100, 2),
        )

    @classmethod
    def run_all_builtin(
        cls, portfolio_weights: dict[str, float], portfolio_value: float = 1_000_000.0,
    ) -> list[StressResult]:
        return [cls.apply_scenario(portfolio_weights, s, portfolio_value) for s in BUILTIN_SCENARIOS]

    @classmethod
    def custom_scenario(cls, name: str, shocks: dict[str, float]) -> StressScenario:
        return StressScenario(name=name, description=f"Custom: {name}", shocks=shocks)
