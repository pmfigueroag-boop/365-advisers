"""
src/engines/autonomous_pm/risk_management_engine.py
──────────────────────────────────────────────────────────────────────────────
Portfolio Risk Management Engine — monitors portfolio risk exposures
and generates violation alerts with remediation suggestions.

Monitors: drawdown, volatility, correlation, concentration (HHI),
          sector exposure.

Integrates with RiskEngine (VaR / CVaR) when return data is available.
"""

from __future__ import annotations

import logging
import math

from src.engines.autonomous_pm.models import (
    APMPortfolio,
    PortfolioRiskReport,
    RiskViolation,
    RiskViolationType,
    RiskViolationSeverity,
)

logger = logging.getLogger("365advisers.apm.risk_management")


# ── Default risk policy ──────────────────────────────────────────────────────

DEFAULT_POLICY = {
    "max_single_position": 0.25,
    "max_sector_weight": 0.40,
    "max_hhi": 0.20,
    "max_portfolio_vol": 0.25,
    "max_drawdown": -0.15,
    "max_correlation_avg": 0.80,
}


class RiskManagementEngine:
    """
    Monitors portfolio risk and generates violation alerts.

    Usage::

        engine = RiskManagementEngine()
        report = engine.assess(
            portfolio=managed_portfolio,
            asset_volatilities=vols,
            correlations=corr,
            returns_history=returns,
        )
    """

    def __init__(self, policy: dict | None = None):
        self.policy = {**DEFAULT_POLICY, **(policy or {})}

    def assess(
        self,
        portfolio: APMPortfolio | None = None,
        asset_volatilities: dict[str, float] | None = None,
        correlations: dict[str, dict[str, float]] | None = None,
        returns_history: list[float] | None = None,
    ) -> PortfolioRiskReport:
        """
        Assess portfolio risk and detect violations.

        Parameters
        ----------
        portfolio : APMPortfolio | None
            The portfolio to assess.
        asset_volatilities : dict | None
            Annualized volatilities per ticker.
        correlations : dict | None
            Pairwise correlations.
        returns_history : list[float] | None
            Portfolio daily return series for drawdown / VaR.
        """
        if portfolio is None or not portfolio.positions:
            return PortfolioRiskReport()

        vols = asset_volatilities or {}
        corr = correlations or {}
        returns = returns_history or []

        violations: list[RiskViolation] = []

        # ── 1. Concentration (HHI) ──────────────────────────────────────
        hhi = sum(p.weight ** 2 for p in portfolio.positions)
        sector_exposures = self._compute_sector_exposures(portfolio)

        if hhi > self.policy["max_hhi"]:
            top_holders = sorted(portfolio.positions, key=lambda p: p.weight, reverse=True)
            violations.append(RiskViolation(
                violation_type=RiskViolationType.CONCENTRATION_BREACH,
                severity=RiskViolationSeverity.WARNING if hhi < 0.30 else RiskViolationSeverity.CRITICAL,
                title="Portfolio Too Concentrated",
                description=f"HHI at {hhi:.3f} exceeds {self.policy['max_hhi']:.3f} limit. Top position: {top_holders[0].ticker} at {top_holders[0].weight:.1%}.",
                affected_tickers=[p.ticker for p in top_holders[:3]],
                current_value=round(hhi, 4),
                threshold=self.policy["max_hhi"],
                remediation="Redistribute weight from top positions to reduce concentration.",
            ))

        # ── 2. Single position cap ───────────────────────────────────────
        for p in portfolio.positions:
            if p.weight > self.policy["max_single_position"]:
                violations.append(RiskViolation(
                    violation_type=RiskViolationType.CONCENTRATION_BREACH,
                    severity=RiskViolationSeverity.WARNING,
                    title=f"{p.ticker} Exceeds Position Limit",
                    description=f"{p.ticker} at {p.weight:.1%} exceeds maximum single position of {self.policy['max_single_position']:.0%}.",
                    affected_tickers=[p.ticker],
                    current_value=round(p.weight, 4),
                    threshold=self.policy["max_single_position"],
                    remediation=f"Reduce {p.ticker} to maximum {self.policy['max_single_position']:.0%}.",
                ))

        # ── 3. Sector overweight ─────────────────────────────────────────
        for sector, wt in sector_exposures.items():
            if wt > self.policy["max_sector_weight"]:
                tickers = [p.ticker for p in portfolio.positions if p.sector == sector]
                violations.append(RiskViolation(
                    violation_type=RiskViolationType.SECTOR_OVERWEIGHT,
                    severity=RiskViolationSeverity.WARNING,
                    title=f"{sector} Sector Overweight",
                    description=f"{sector} at {wt:.1%} exceeds {self.policy['max_sector_weight']:.0%} limit.",
                    affected_tickers=tickers[:5],
                    current_value=round(wt, 4),
                    threshold=self.policy["max_sector_weight"],
                    remediation=f"Reduce {sector} exposure by rotating into other sectors.",
                ))

        # ── 4. Portfolio volatility ──────────────────────────────────────
        port_vol = self._estimate_portfolio_vol(portfolio, vols, corr)
        if port_vol > self.policy["max_portfolio_vol"]:
            violations.append(RiskViolation(
                violation_type=RiskViolationType.VOLATILITY_EXCESS,
                severity=RiskViolationSeverity.CRITICAL if port_vol > 0.35 else RiskViolationSeverity.WARNING,
                title="Excessive Portfolio Volatility",
                description=f"Estimated volatility at {port_vol:.1%} exceeds {self.policy['max_portfolio_vol']:.0%} limit.",
                current_value=round(port_vol, 4),
                threshold=self.policy["max_portfolio_vol"],
                remediation="Increase allocation to low-volatility assets or add hedges.",
            ))

        # ── 5. Drawdown ─────────────────────────────────────────────────
        max_dd = 0.0
        if returns:
            max_dd = self._compute_max_drawdown(returns)
            if max_dd < self.policy["max_drawdown"]:
                violations.append(RiskViolation(
                    violation_type=RiskViolationType.DRAWDOWN_WARNING,
                    severity=RiskViolationSeverity.CRITICAL if max_dd < -0.25 else RiskViolationSeverity.WARNING,
                    title="Maximum Drawdown Exceeded",
                    description=f"Portfolio drawdown at {max_dd:.1%} breaches {self.policy['max_drawdown']:.0%} limit.",
                    current_value=round(max_dd, 4),
                    threshold=self.policy["max_drawdown"],
                    remediation="Consider de-risking: reduce equity exposure, increase cash buffer.",
                ))

        # ── 6. Correlation ───────────────────────────────────────────────
        avg_corr = self._avg_correlation(portfolio, corr)
        if avg_corr > self.policy["max_correlation_avg"]:
            violations.append(RiskViolation(
                violation_type=RiskViolationType.CORRELATION_SPIKE,
                severity=RiskViolationSeverity.WARNING,
                title="High Average Correlation",
                description=f"Average pairwise correlation at {avg_corr:.2f} exceeds {self.policy['max_correlation_avg']} limit.",
                current_value=round(avg_corr, 4),
                threshold=self.policy["max_correlation_avg"],
                remediation="Add uncorrelated assets (bonds, commodities, alternatives) to improve diversification.",
            ))

        # ── Compute risk score ───────────────────────────────────────────
        risk_score = self._compute_risk_score(violations, port_vol, hhi, max_dd)
        within_limits = len(violations) == 0

        # ── VaR / CVaR (if return data available) ────────────────────────
        var_95 = 0.0
        cvar_95 = 0.0
        if returns and len(returns) > 20:
            sorted_r = sorted(returns)
            idx = max(int(len(sorted_r) * 0.05), 1)
            var_95 = round(sorted_r[idx - 1], 6)
            cvar_95 = round(sum(sorted_r[:idx]) / idx, 6) if idx > 0 else 0.0

        return PortfolioRiskReport(
            portfolio_volatility=round(port_vol, 4),
            max_drawdown=round(max_dd, 4),
            var_95=var_95,
            cvar_95=cvar_95,
            concentration_hhi=round(hhi, 4),
            sector_exposures=sector_exposures,
            violations=violations,
            risk_score=round(risk_score, 1),
            within_limits=within_limits,
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _compute_sector_exposures(portfolio: APMPortfolio) -> dict[str, float]:
        sectors: dict[str, float] = {}
        for p in portfolio.positions:
            s = p.sector or "Unknown"
            sectors[s] = round(sectors.get(s, 0) + p.weight, 4)
        return sectors

    @staticmethod
    def _estimate_portfolio_vol(
        portfolio: APMPortfolio,
        vols: dict[str, float],
        corr: dict[str, dict[str, float]],
    ) -> float:
        weighted_var = 0.0
        positions = portfolio.positions
        for p in positions:
            v = vols.get(p.ticker, 0.15)
            weighted_var += (p.weight * v) ** 2
        for i, p1 in enumerate(positions):
            for p2 in positions[i + 1:]:
                c = corr.get(p1.ticker, {}).get(p2.ticker, 0.3)
                v1 = vols.get(p1.ticker, 0.15)
                v2 = vols.get(p2.ticker, 0.15)
                weighted_var += 2 * p1.weight * p2.weight * v1 * v2 * c
        return math.sqrt(max(weighted_var, 0))

    @staticmethod
    def _compute_max_drawdown(returns: list[float]) -> float:
        if not returns:
            return 0.0
        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0
        for r in returns:
            cumulative *= (1 + r)
            peak = max(peak, cumulative)
            dd = (cumulative - peak) / peak
            max_dd = min(max_dd, dd)
        return max_dd

    @staticmethod
    def _avg_correlation(
        portfolio: APMPortfolio,
        corr: dict[str, dict[str, float]],
    ) -> float:
        positions = portfolio.positions
        if len(positions) < 2:
            return 0.0
        total = 0.0
        count = 0
        for i, p1 in enumerate(positions):
            for p2 in positions[i + 1:]:
                c = corr.get(p1.ticker, {}).get(p2.ticker, 0.3)
                total += c
                count += 1
        return total / count if count > 0 else 0.0

    @staticmethod
    def _compute_risk_score(
        violations: list[RiskViolation],
        port_vol: float,
        hhi: float,
        max_dd: float,
    ) -> float:
        """0-100 risk score. Higher = more risk."""
        score = 0.0
        # Violation-based
        for v in violations:
            if v.severity == RiskViolationSeverity.CRITICAL:
                score += 25
            elif v.severity == RiskViolationSeverity.WARNING:
                score += 12
            else:
                score += 5
        # Metric-based
        score += port_vol * 100  # 15% vol → 15pts
        score += hhi * 50  # HHI 0.2 → 10pts
        score += abs(max_dd) * 80  # -10% drawdown → 8pts
        return min(score, 100.0)
