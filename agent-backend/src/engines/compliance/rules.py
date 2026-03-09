"""
src/engines/compliance/rules.py — Built-in compliance rules.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from src.engines.compliance.models import ComplianceRule, RuleType, ComplianceCheck

logger = logging.getLogger("365advisers.compliance.rules")


class ComplianceRuleEngine:
    """Evaluate compliance rules against portfolio state."""

    @classmethod
    def check_restricted_list(
        cls, rule: ComplianceRule,
        positions: dict[str, float],
    ) -> ComplianceCheck:
        """Check if any position is on the restricted list."""
        restricted = set(rule.params.get("tickers", []))
        violations = [t for t in positions if t in restricted and positions[t] != 0]
        return ComplianceCheck(
            rule_id=rule.rule_id, rule_type=rule.rule_type,
            passed=len(violations) == 0,
            severity="critical" if violations else "info",
            message=f"Restricted positions: {violations}" if violations else "No restricted positions",
            details={"violations": violations},
        )

    @classmethod
    def check_position_limit(
        cls, rule: ComplianceRule,
        weights: dict[str, float],
    ) -> ComplianceCheck:
        """Check if any single position exceeds the limit."""
        max_weight = rule.params.get("max_weight", 0.10)
        violations = {t: w for t, w in weights.items() if abs(w) > max_weight}
        return ComplianceCheck(
            rule_id=rule.rule_id, rule_type=rule.rule_type,
            passed=len(violations) == 0,
            severity="warning" if violations else "info",
            message=f"Position limit violations ({max_weight:.0%}): {list(violations.keys())}" if violations else "All positions within limits",
            details={"max_weight": max_weight, "violations": violations},
        )

    @classmethod
    def check_sector_limit(
        cls, rule: ComplianceRule,
        sector_weights: dict[str, float],
    ) -> ComplianceCheck:
        """Check if any sector exceeds its limit."""
        max_sector = rule.params.get("max_sector_weight", 0.30)
        violations = {s: w for s, w in sector_weights.items() if abs(w) > max_sector}
        return ComplianceCheck(
            rule_id=rule.rule_id, rule_type=rule.rule_type,
            passed=len(violations) == 0,
            severity="warning" if violations else "info",
            message=f"Sector limit breaches ({max_sector:.0%}): {list(violations.keys())}" if violations else "All sectors within limits",
            details={"max_sector_weight": max_sector, "violations": violations},
        )

    @classmethod
    def check_concentration(
        cls, rule: ComplianceRule,
        weights: dict[str, float],
    ) -> ComplianceCheck:
        """Check portfolio concentration (HHI)."""
        max_hhi = rule.params.get("max_hhi", 0.15)
        hhi = sum(w ** 2 for w in weights.values())
        return ComplianceCheck(
            rule_id=rule.rule_id, rule_type=rule.rule_type,
            passed=hhi <= max_hhi,
            severity="warning" if hhi > max_hhi else "info",
            message=f"HHI={hhi:.4f} {'exceeds' if hhi > max_hhi else 'within'} limit {max_hhi:.4f}",
            details={"hhi": round(hhi, 6), "max_hhi": max_hhi},
        )

    @classmethod
    def check_leverage(
        cls, rule: ComplianceRule,
        gross_exposure: float,
    ) -> ComplianceCheck:
        """Check if gross exposure exceeds leverage limit."""
        max_leverage = rule.params.get("max_leverage", 2.0)
        return ComplianceCheck(
            rule_id=rule.rule_id, rule_type=rule.rule_type,
            passed=gross_exposure <= max_leverage,
            severity="critical" if gross_exposure > max_leverage else "info",
            message=f"Gross exposure {gross_exposure:.2f}x {'exceeds' if gross_exposure > max_leverage else 'within'} {max_leverage:.2f}x limit",
            details={"gross_exposure": gross_exposure, "max_leverage": max_leverage},
        )

    @classmethod
    def check_holding_period(
        cls, rule: ComplianceRule,
        trades: list[dict],
    ) -> ComplianceCheck:
        """Check if any trade violates minimum holding period."""
        min_days = rule.params.get("min_holding_days", 1)
        violations = [t for t in trades if t.get("holding_days", 999) < min_days]
        return ComplianceCheck(
            rule_id=rule.rule_id, rule_type=rule.rule_type,
            passed=len(violations) == 0,
            severity="warning" if violations else "info",
            message=f"{len(violations)} trades below {min_days}-day holding period" if violations else "All trades meet holding period",
            details={"min_days": min_days, "violations_count": len(violations)},
        )

    @classmethod
    def check_trade_frequency(
        cls, rule: ComplianceRule,
        trades_today: int,
    ) -> ComplianceCheck:
        """Check daily trade count limit."""
        max_trades = rule.params.get("max_daily_trades", 100)
        return ComplianceCheck(
            rule_id=rule.rule_id, rule_type=rule.rule_type,
            passed=trades_today <= max_trades,
            severity="warning" if trades_today > max_trades else "info",
            message=f"{trades_today} trades today {'exceeds' if trades_today > max_trades else 'within'} {max_trades} limit",
            details={"trades_today": trades_today, "max_daily_trades": max_trades},
        )
