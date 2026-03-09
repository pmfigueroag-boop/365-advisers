"""
src/engines/compliance/engine.py — Compliance Engine orchestrator.
"""
from __future__ import annotations
import logging
from src.engines.compliance.models import ComplianceRule, RuleType, ComplianceCheck, ComplianceReport
from src.engines.compliance.rules import ComplianceRuleEngine

logger = logging.getLogger("365advisers.compliance.engine")


# Default rule set
DEFAULT_RULES = [
    ComplianceRule(rule_id="RL-001", rule_type=RuleType.RESTRICTED_LIST, description="Restricted securities list", params={"tickers": []}),
    ComplianceRule(rule_id="PL-001", rule_type=RuleType.POSITION_LIMIT, description="Max 10% per position", params={"max_weight": 0.10}),
    ComplianceRule(rule_id="SL-001", rule_type=RuleType.SECTOR_LIMIT, description="Max 30% per sector", params={"max_sector_weight": 0.30}),
    ComplianceRule(rule_id="CC-001", rule_type=RuleType.CONCENTRATION, description="Max HHI 0.15", params={"max_hhi": 0.15}),
    ComplianceRule(rule_id="LV-001", rule_type=RuleType.LEVERAGE, description="Max 2x gross leverage", params={"max_leverage": 2.0}),
    ComplianceRule(rule_id="HP-001", rule_type=RuleType.HOLDING_PERIOD, description="Min 1-day holding", params={"min_holding_days": 1}),
    ComplianceRule(rule_id="TF-001", rule_type=RuleType.TRADE_FREQUENCY, description="Max 100 trades/day", params={"max_daily_trades": 100}),
]


class ComplianceEngine:
    """Run compliance checks against portfolio state."""

    def __init__(self, rules: list[ComplianceRule] | None = None):
        self.rules = rules or list(DEFAULT_RULES)

    def add_rule(self, rule: ComplianceRule):
        self.rules.append(rule)

    def remove_rule(self, rule_id: str):
        self.rules = [r for r in self.rules if r.rule_id != rule_id]

    def run_all(
        self,
        weights: dict[str, float] | None = None,
        positions: dict[str, float] | None = None,
        sector_weights: dict[str, float] | None = None,
        gross_exposure: float = 1.0,
        trades: list[dict] | None = None,
        trades_today: int = 0,
    ) -> ComplianceReport:
        """Run all enabled rules and produce a report."""
        checks: list[ComplianceCheck] = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            check = self._evaluate(rule, weights, positions, sector_weights, gross_exposure, trades, trades_today)
            if check:
                checks.append(check)

        passed = sum(1 for c in checks if c.passed)
        failed = sum(1 for c in checks if not c.passed)
        warnings = sum(1 for c in checks if not c.passed and c.severity == "warning")
        critical = sum(1 for c in checks if not c.passed and c.severity == "critical")

        return ComplianceReport(
            total_rules=len(checks),
            passed=passed, failed=failed,
            warnings=warnings, critical=critical,
            is_compliant=critical == 0,
            checks=checks,
        )

    def _evaluate(self, rule, weights, positions, sector_weights, gross_exposure, trades, trades_today) -> ComplianceCheck | None:
        try:
            if rule.rule_type == RuleType.RESTRICTED_LIST and positions:
                return ComplianceRuleEngine.check_restricted_list(rule, positions)
            elif rule.rule_type == RuleType.POSITION_LIMIT and weights:
                return ComplianceRuleEngine.check_position_limit(rule, weights)
            elif rule.rule_type == RuleType.SECTOR_LIMIT and sector_weights:
                return ComplianceRuleEngine.check_sector_limit(rule, sector_weights)
            elif rule.rule_type == RuleType.CONCENTRATION and weights:
                return ComplianceRuleEngine.check_concentration(rule, weights)
            elif rule.rule_type == RuleType.LEVERAGE:
                return ComplianceRuleEngine.check_leverage(rule, gross_exposure)
            elif rule.rule_type == RuleType.HOLDING_PERIOD and trades:
                return ComplianceRuleEngine.check_holding_period(rule, trades)
            elif rule.rule_type == RuleType.TRADE_FREQUENCY:
                return ComplianceRuleEngine.check_trade_frequency(rule, trades_today)
        except Exception as e:
            logger.error("Rule %s failed: %s", rule.rule_id, e)
        return None
