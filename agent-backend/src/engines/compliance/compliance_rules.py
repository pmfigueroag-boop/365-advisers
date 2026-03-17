"""
src/engines/compliance/compliance_rules.py
--------------------------------------------------------------------------
Compliance Rule Engine — codified investment restrictions.

Rules enforced:
  - Max sector exposure (default 30%)
  - Max single position (default 10%)
  - Restricted ticker list (sanctions, ESG, internal)
  - Min diversification (at least N positions)
  - Max portfolio beta range
  - Max turnover per period

Every rule check produces:
  - PASS/FAIL
  - Violation description
  - Suggested remedy

Integration: pre-trade (before rebalance) and post-trade (compliance check).

Usage::

    engine = ComplianceRuleEngine()
    report = engine.check_portfolio(weights, metadata)
"""

from __future__ import annotations

import logging
from collections import defaultdict

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.compliance.rules")


# ── Contracts ────────────────────────────────────────────────────────────────

class ComplianceConfig(BaseModel):
    """Configurable compliance limits."""
    max_single_position: float = Field(0.10, description="Max 10% in one name")
    max_sector_exposure: float = Field(0.30, description="Max 30% in one sector")
    min_positions: int = Field(5, description="At least 5 positions")
    max_positions: int = Field(50, description="At most 50 positions")
    max_portfolio_beta: float = Field(1.5, description="Max portfolio beta")
    min_portfolio_beta: float = Field(-0.5, description="Min portfolio beta")
    max_turnover: float = Field(0.50, description="Max turnover per rebalance")
    restricted_tickers: list[str] = Field(default_factory=list)


class RuleResult(BaseModel):
    """Result of a single rule check."""
    rule_name: str
    passed: bool = True
    severity: str = "info"   # info, warning, violation, critical
    description: str = ""
    current_value: float | str = ""
    limit_value: float | str = ""
    remedy: str = ""


class ComplianceReport(BaseModel):
    """Complete compliance report."""
    results: list[RuleResult] = Field(default_factory=list)
    total_rules: int = 0
    passed: int = 0
    warnings: int = 0
    violations: int = 0
    critical: int = 0
    is_compliant: bool = True
    check_type: str = "pre_trade"


# ── Engine ───────────────────────────────────────────────────────────────────

class ComplianceRuleEngine:
    """
    Pre-trade and post-trade compliance checks.

    Runs a set of configurable rules against portfolio weights and metadata.
    """

    def __init__(self, config: ComplianceConfig | None = None) -> None:
        self.config = config or ComplianceConfig()

    def check_portfolio(
        self,
        weights: dict[str, float],
        sector_map: dict[str, str] | None = None,
        betas: dict[str, float] | None = None,
        turnover: float = 0.0,
        check_type: str = "pre_trade",
    ) -> ComplianceReport:
        """
        Run all compliance rules.

        Parameters
        ----------
        weights : dict[str, float]
            Portfolio weights.
        sector_map : dict[str, str] | None
            {ticker: sector}.
        betas : dict[str, float] | None
            {ticker: beta}.
        turnover : float
            Current rebalance turnover.
        check_type : str
            "pre_trade" or "post_trade".
        """
        results: list[RuleResult] = []

        results.append(self._check_single_position(weights))
        results.append(self._check_min_positions(weights))
        results.append(self._check_max_positions(weights))
        results.append(self._check_restricted(weights))

        if sector_map:
            results.append(self._check_sector_exposure(weights, sector_map))

        if betas:
            results.append(self._check_portfolio_beta(weights, betas))

        if turnover > 0:
            results.append(self._check_turnover(turnover))

        n_pass = sum(1 for r in results if r.passed)
        n_warn = sum(1 for r in results if r.severity == "warning")
        n_viol = sum(1 for r in results if r.severity == "violation")
        n_crit = sum(1 for r in results if r.severity == "critical")

        is_compliant = n_viol == 0 and n_crit == 0

        logger.info(
            "COMPLIANCE [%s]: %d rules — %d pass, %d warn, %d violation, "
            "%d critical → %s",
            check_type, len(results), n_pass, n_warn, n_viol, n_crit,
            "COMPLIANT" if is_compliant else "NON-COMPLIANT",
        )

        return ComplianceReport(
            results=results,
            total_rules=len(results),
            passed=n_pass,
            warnings=n_warn,
            violations=n_viol,
            critical=n_crit,
            is_compliant=is_compliant,
            check_type=check_type,
        )

    def _check_single_position(self, weights: dict[str, float]) -> RuleResult:
        """Max single position limit."""
        max_w = max(weights.values()) if weights else 0.0
        max_ticker = max(weights, key=weights.get) if weights else ""
        limit = self.config.max_single_position

        if max_w > limit:
            return RuleResult(
                rule_name="max_single_position",
                passed=False,
                severity="violation",
                description=f"{max_ticker} at {max_w:.1%} exceeds {limit:.0%} limit",
                current_value=round(max_w, 4),
                limit_value=limit,
                remedy=f"Reduce {max_ticker} to ≤{limit:.0%}",
            )
        return RuleResult(
            rule_name="max_single_position",
            passed=True,
            description=f"Largest position: {max_ticker} at {max_w:.1%}",
            current_value=round(max_w, 4),
            limit_value=limit,
        )

    def _check_sector_exposure(
        self,
        weights: dict[str, float],
        sector_map: dict[str, str],
    ) -> RuleResult:
        """Max sector exposure limit."""
        sector_weights: dict[str, float] = defaultdict(float)
        for ticker, w in weights.items():
            sector = sector_map.get(ticker, "Unknown")
            sector_weights[sector] += w

        if not sector_weights:
            return RuleResult(rule_name="max_sector_exposure", passed=True)

        max_sector = max(sector_weights, key=sector_weights.get)
        max_exp = sector_weights[max_sector]
        limit = self.config.max_sector_exposure

        if max_exp > limit:
            return RuleResult(
                rule_name="max_sector_exposure",
                passed=False,
                severity="violation",
                description=f"{max_sector} at {max_exp:.1%} exceeds {limit:.0%}",
                current_value=round(max_exp, 4),
                limit_value=limit,
                remedy=f"Reduce {max_sector} exposure to ≤{limit:.0%}",
            )
        return RuleResult(
            rule_name="max_sector_exposure",
            passed=True,
            description=f"Largest sector: {max_sector} at {max_exp:.1%}",
            current_value=round(max_exp, 4),
            limit_value=limit,
        )

    def _check_min_positions(self, weights: dict[str, float]) -> RuleResult:
        """Minimum diversification."""
        n = sum(1 for w in weights.values() if w > 0.005)
        limit = self.config.min_positions

        if n < limit:
            return RuleResult(
                rule_name="min_positions",
                passed=False,
                severity="violation",
                description=f"{n} positions below minimum {limit}",
                current_value=n,
                limit_value=limit,
                remedy=f"Add at least {limit - n} more positions",
            )
        return RuleResult(
            rule_name="min_positions", passed=True,
            description=f"{n} positions (min={limit})",
            current_value=n, limit_value=limit,
        )

    def _check_max_positions(self, weights: dict[str, float]) -> RuleResult:
        """Maximum positions."""
        n = sum(1 for w in weights.values() if w > 0.005)
        limit = self.config.max_positions

        if n > limit:
            return RuleResult(
                rule_name="max_positions",
                passed=False, severity="warning",
                description=f"{n} positions exceeds maximum {limit}",
                current_value=n, limit_value=limit,
                remedy=f"Reduce to ≤{limit} positions",
            )
        return RuleResult(
            rule_name="max_positions", passed=True,
            description=f"{n} positions (max={limit})",
            current_value=n, limit_value=limit,
        )

    def _check_restricted(self, weights: dict[str, float]) -> RuleResult:
        """Restricted ticker list."""
        restricted = self.config.restricted_tickers
        violations = [t for t in weights if t in restricted and weights[t] > 0.001]

        if violations:
            return RuleResult(
                rule_name="restricted_tickers",
                passed=False,
                severity="critical",
                description=f"Restricted tickers in portfolio: {', '.join(violations)}",
                current_value=", ".join(violations),
                limit_value="none allowed",
                remedy=f"Remove {', '.join(violations)} immediately",
            )
        return RuleResult(
            rule_name="restricted_tickers", passed=True,
            description="No restricted tickers",
        )

    def _check_portfolio_beta(
        self,
        weights: dict[str, float],
        betas: dict[str, float],
    ) -> RuleResult:
        """Portfolio beta range."""
        port_beta = sum(weights.get(t, 0) * betas.get(t, 1) for t in weights)
        lo = self.config.min_portfolio_beta
        hi = self.config.max_portfolio_beta

        if port_beta < lo or port_beta > hi:
            return RuleResult(
                rule_name="portfolio_beta_range",
                passed=False, severity="violation",
                description=f"Beta {port_beta:.2f} outside [{lo:.1f}, {hi:.1f}]",
                current_value=round(port_beta, 4),
                limit_value=f"[{lo}, {hi}]",
                remedy=f"Adjust beta to within [{lo:.1f}, {hi:.1f}]",
            )
        return RuleResult(
            rule_name="portfolio_beta_range", passed=True,
            description=f"Beta {port_beta:.2f} within [{lo:.1f}, {hi:.1f}]",
            current_value=round(port_beta, 4), limit_value=f"[{lo}, {hi}]",
        )

    def _check_turnover(self, turnover: float) -> RuleResult:
        """Max turnover per rebalance."""
        limit = self.config.max_turnover
        if turnover > limit:
            return RuleResult(
                rule_name="max_turnover",
                passed=False, severity="warning",
                description=f"Turnover {turnover:.1%} exceeds {limit:.0%}",
                current_value=round(turnover, 4), limit_value=limit,
                remedy=f"Use gradual transition (multi-period rebalance)",
            )
        return RuleResult(
            rule_name="max_turnover", passed=True,
            description=f"Turnover {turnover:.1%} within {limit:.0%}",
            current_value=round(turnover, 4), limit_value=limit,
        )
