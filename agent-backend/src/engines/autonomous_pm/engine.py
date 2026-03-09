"""
src/engines/autonomous_pm/engine.py
──────────────────────────────────────────────────────────────────────────────
AutonomousPortfolioManager — master facade orchestrating the 5 APM
sub-engines into a unified portfolio management pipeline.

Pipeline:
  Investment Brain → regime + opportunities ─┐
  SuperAlpha → alpha profiles ───────────────┤
                                             ├→ Construction Engine
                                             ├→ Allocation Engine
                                             ├→ Risk Management Engine
                                             ├→ Rebalancing Engine
                                             ├→ Performance Engine
                                             └→ APMDashboard

Every decision is explainable with full signal provenance.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.investment_brain.engine import InvestmentBrain
from src.engines.investment_brain.models import MarketRegime

from src.engines.autonomous_pm.allocation_engine import AllocationEngine
from src.engines.autonomous_pm.construction_engine import ConstructionEngine
from src.engines.autonomous_pm.models import (
    APMDashboard,
    APMPortfolio,
    PortfolioObjective,
)
from src.engines.autonomous_pm.performance_engine import PerformanceEngine
from src.engines.autonomous_pm.rebalancing_engine import RebalancingEngine
from src.engines.autonomous_pm.risk_management_engine import RiskManagementEngine

logger = logging.getLogger("365advisers.apm")


class AutonomousPortfolioManager:
    """
    AI-Driven Portfolio Management facade.

    Integrates the Investment Brain's interpretation layer with 5 portfolio
    management sub-engines to construct, allocate, rebalance, monitor,
    and evaluate portfolios autonomously.

    Usage::

        apm = AutonomousPortfolioManager()
        dashboard = apm.manage(
            alpha_profiles=profiles,
            macro_data=macro,
            vol_data=vol,
            regime="expansion",
        )
    """

    def __init__(self) -> None:
        self.construction = ConstructionEngine()
        self.allocation = AllocationEngine()
        self.rebalancing = RebalancingEngine()
        self.risk_management = RiskManagementEngine()
        self.performance = PerformanceEngine()

    # ── Full pipeline ────────────────────────────────────────────────────

    def manage(
        self,
        alpha_profiles: list[dict] | None = None,
        regime: str = "expansion",
        previous_regime: str | None = None,
        opportunities: list[dict] | None = None,
        risk_alerts: list[dict] | None = None,
        asset_volatilities: dict[str, float] | None = None,
        correlations: dict[str, dict[str, float]] | None = None,
        portfolio_returns: list[float] | None = None,
        benchmark_returns: list[float] | None = None,
        existing_portfolio: APMPortfolio | None = None,
        market_events: list[dict] | None = None,
        objectives: list[PortfolioObjective] | None = None,
    ) -> APMDashboard:
        """
        Run the complete APM pipeline.

        Parameters
        ----------
        alpha_profiles : list[dict] | None
            SuperAlpha profiles for construction.
        regime : str
            Current market regime.
        previous_regime : str | None
            Previous regime (for rebalance trigger detection).
        opportunities : list[dict] | None
            Investment Brain opportunities.
        risk_alerts : list[dict] | None
            Investment Brain risk alerts.
        asset_volatilities : dict | None
            Per-asset annualized vols.
        correlations : dict | None
            Pairwise correlation matrix.
        portfolio_returns : list[float] | None
            Historical daily portfolio returns.
        benchmark_returns : list[float] | None
            Historical daily benchmark returns.
        existing_portfolio : APMPortfolio | None
            Existing portfolio for rebalancing evaluation.
        market_events : list[dict] | None
            Recent market events.
        objectives : list[PortfolioObjective] | None
            Specific objectives to construct (default: all 6).
        """
        profiles = alpha_profiles or []
        opps = opportunities or []
        vols = asset_volatilities or {}
        corr = correlations or {}
        p_returns = portfolio_returns or []
        b_returns = benchmark_returns or []
        events = market_events or []

        logger.info("APM pipeline: %d profiles, regime=%s", len(profiles), regime)

        explanations: list[str] = []

        # ── Stage 1: Portfolio Construction ──────────────────────────────
        targets = objectives or list(PortfolioObjective)
        portfolios: list[APMPortfolio] = []

        for obj in targets:
            p = self.construction.construct(
                objective=obj,
                alpha_profiles=profiles,
                regime=regime,
                opportunities=opps,
            )
            portfolios.append(p)

        explanations.append(f"Constructed {len(portfolios)} portfolios using {len(profiles)} alpha candidates in {regime} regime.")

        # ── Stage 2: Asset Allocation ────────────────────────────────────
        for p in portfolios:
            if p.positions:
                self.allocation.optimise(
                    portfolio=p,
                    asset_volatilities=vols,
                    correlations=corr,
                    regime=regime,
                )

        explanations.append(f"Optimised weights using regime-adjusted allocation methods.")

        # ── Stage 3: Risk Assessment ─────────────────────────────────────
        # Assess the primary portfolio (first with positions)
        primary = next((p for p in portfolios if p.positions), None)
        risk_report = None
        if primary:
            risk_report = self.risk_management.assess(
                portfolio=primary,
                asset_volatilities=vols,
                correlations=corr,
                returns_history=p_returns if p_returns else None,
            )
            violation_count = len(risk_report.violations)
            explanations.append(
                f"Risk assessment: score={risk_report.risk_score:.0f}/100, "
                f"{violation_count} violation(s), HHI={risk_report.concentration_hhi:.3f}."
            )

        # ── Stage 4: Rebalancing Evaluation ──────────────────────────────
        rebalance_target = existing_portfolio or primary
        rebalance = None
        if rebalance_target:
            rebalance = self.rebalancing.evaluate(
                current_portfolio=rebalance_target,
                new_alpha_profiles=profiles,
                current_regime=regime,
                previous_regime=previous_regime,
                risk_report=risk_report,
                market_events=events,
            )
            if rebalance.should_rebalance:
                explanations.append(
                    f"Rebalance recommended ({rebalance.urgency.value} urgency): "
                    f"{len(rebalance.triggers_fired)} trigger(s) fired, "
                    f"{len(rebalance.actions)} action(s)."
                )
            else:
                explanations.append("No rebalancing required at this time.")

        # ── Stage 5: Performance Analysis ────────────────────────────────
        perf = None
        if p_returns:
            perf = self.performance.evaluate(
                portfolio_returns=p_returns,
                benchmark_returns=b_returns,
            )
            explanations.append(
                f"Performance: return={perf.total_return:.2%}, "
                f"Sharpe={perf.sharpe_ratio:.2f}, "
                f"alpha={perf.alpha_vs_benchmark:.2%}."
            )

        # ── Stage 6: Explainability ──────────────────────────────────────
        explanations.extend(self._generate_explanations(portfolios, risk_report, rebalance, regime))

        logger.info("APM pipeline complete: %d portfolios, %d explanations", len(portfolios), len(explanations))

        return APMDashboard(
            portfolios=portfolios,
            rebalance=rebalance,
            risk_report=risk_report,
            performance=perf,
            explanations=explanations,
            asset_count=len(profiles),
            active_regime=regime,
        )

    # ── Explainability ───────────────────────────────────────────────────

    @staticmethod
    def _generate_explanations(
        portfolios: list[APMPortfolio],
        risk_report,
        rebalance,
        regime: str,
    ) -> list[str]:
        """Generate human-readable explanations for APM decisions."""
        explanations: list[str] = []

        # Portfolio selection rationale
        for p in portfolios:
            if p.positions:
                top = sorted(p.positions, key=lambda x: x.alpha_score, reverse=True)[:3]
                tickers = [t.ticker for t in top]
                explanations.append(
                    f"{p.objective.value.title()} portfolio: top positions {', '.join(tickers)} "
                    f"selected via {p.allocation_method.value} method."
                )

        # Risk-driven explanations
        if risk_report and risk_report.violations:
            for v in risk_report.violations[:3]:
                explanations.append(
                    f"⚠️ {v.title}: {v.description.split('.')[0]}. "
                    f"Recommendation: {v.remediation.split('.')[0]}."
                )

        # Regime-based positioning
        regime_advice = {
            "expansion": "Portfolios tilted toward growth and cyclical sectors — expansion regime supports risk-on positioning.",
            "slowdown": "Defensive tilt applied — slowdown conditions favor quality and income assets.",
            "recession": "Maximum defensive positioning — preservation of capital is the primary objective.",
            "recovery": "Early-cycle positioning — financials and industrials typically lead recovery.",
            "high_volatility": "Risk reduction active — reduced position sizes and increased quality bias.",
            "liquidity_expansion": "Growth emphasis — abundant liquidity supports risk assets and innovation sectors.",
        }
        advice = regime_advice.get(regime)
        if advice:
            explanations.append(advice)

        return explanations
