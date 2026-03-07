"""
src/engines/strategy_research/rules.py
─────────────────────────────────────────────────────────────────────────────
RuleEngine — Evaluate declarative entry/exit rules and regime actions.

Rules are defined as Pydantic models in strategy/definition.py and
evaluated against opportunity dicts or portfolio positions.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("365advisers.strategy_research.rules")

# ── Operator registry ────────────────────────────────────────────────────────

OPERATORS = {
    "gt":     lambda a, b: a > b,
    "lt":     lambda a, b: a < b,
    "gte":    lambda a, b: a >= b,
    "lte":    lambda a, b: a <= b,
    "eq":     lambda a, b: a == b,
    "neq":    lambda a, b: a != b,
    "in":     lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


class RuleEngine:
    """Evaluate declarative entry/exit rules against market data."""

    # ── Entry Rules ──────────────────────────────────────────────────────

    @staticmethod
    def evaluate_entry(
        opportunity: dict[str, Any],
        entry_rules: list[dict],
    ) -> dict:
        """Evaluate whether an opportunity passes all entry rules.

        Args:
            opportunity: Opportunity dict with fields like case_score, uos, etc.
            entry_rules: List of EntryRule dicts from StrategyConfig

        Returns:
            {passed: bool, results: [{rule, field, value, threshold, passed}]}
        """
        if not entry_rules:
            return {"passed": True, "results": [], "rules_evaluated": 0}

        sorted_rules = sorted(entry_rules, key=lambda r: r.get("priority", 0))
        results = []
        all_passed = True

        for rule in sorted_rules:
            field = rule.get("field", "")
            operator = rule.get("operator", "gte")
            threshold = rule.get("value", 0)

            actual_value = opportunity.get(field)
            if actual_value is None:
                # Field missing — rule fails
                results.append({
                    "field": field,
                    "operator": operator,
                    "threshold": threshold,
                    "actual": None,
                    "passed": False,
                    "reason": f"Field '{field}' not found",
                })
                all_passed = False
                continue

            op_fn = OPERATORS.get(operator)
            if not op_fn:
                results.append({
                    "field": field,
                    "operator": operator,
                    "threshold": threshold,
                    "actual": actual_value,
                    "passed": False,
                    "reason": f"Unknown operator '{operator}'",
                })
                all_passed = False
                continue

            try:
                passed = op_fn(actual_value, threshold)
            except (TypeError, ValueError):
                passed = False

            results.append({
                "field": field,
                "operator": operator,
                "threshold": threshold,
                "actual": actual_value,
                "passed": passed,
            })

            if not passed:
                all_passed = False

        return {
            "passed": all_passed,
            "results": results,
            "rules_evaluated": len(results),
        }

    @staticmethod
    def filter_opportunities(
        opportunities: list[dict],
        entry_rules: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """Filter opportunities through entry rules.

        Returns:
            (passed, rejected) tuple of opportunity lists
        """
        passed = []
        rejected = []

        for opp in opportunities:
            result = RuleEngine.evaluate_entry(opp, entry_rules)
            if result["passed"]:
                passed.append({**opp, "_entry_evaluation": result})
            else:
                rejected.append({**opp, "_entry_evaluation": result})

        return passed, rejected

    # ── Exit Rules ───────────────────────────────────────────────────────

    @staticmethod
    def evaluate_exit(
        position: dict[str, Any],
        exit_rules: list[dict],
        current_date: str | None = None,
    ) -> dict:
        """Evaluate whether a position should be exited.

        Args:
            position: {ticker, entry_date, entry_price, current_price, unrealized_pnl_pct, ...}
            exit_rules: List of ExitRule dicts from StrategyConfig
            current_date: Current evaluation date (YYYY-MM-DD)

        Returns:
            {should_exit: bool, triggered_rules: [...]}
        """
        if not exit_rules:
            return {"should_exit": False, "triggered_rules": []}

        triggered = []

        for rule in exit_rules:
            rule_type = rule.get("rule_type", "")
            params = rule.get("params", {})

            if rule_type == "trailing_stop":
                pct = params.get("pct", 0.15)
                max_return = position.get("max_unrealized_pnl_pct", 0.0)
                current_return = position.get("unrealized_pnl_pct", 0.0)
                drawdown_from_peak = max_return - current_return

                if drawdown_from_peak >= pct and max_return > 0:
                    triggered.append({
                        "rule_type": "trailing_stop",
                        "threshold": pct,
                        "drawdown_from_peak": round(drawdown_from_peak, 4),
                    })

            elif rule_type == "time_stop":
                max_days = params.get("days", 60)
                days_held = position.get("days_held", 0)

                if days_held >= max_days:
                    triggered.append({
                        "rule_type": "time_stop",
                        "threshold_days": max_days,
                        "days_held": days_held,
                    })

            elif rule_type == "target_reached":
                target_pct = params.get("return_pct", 0.30)
                current_return = position.get("unrealized_pnl_pct", 0.0)

                if current_return >= target_pct:
                    triggered.append({
                        "rule_type": "target_reached",
                        "target_pct": target_pct,
                        "current_return": round(current_return, 4),
                    })

            elif rule_type == "signal_reversal":
                required_cats = set(params.get("signal_categories", []))
                active_cats = set(position.get("active_signal_categories", []))

                if required_cats and not required_cats.issubset(active_cats):
                    triggered.append({
                        "rule_type": "signal_reversal",
                        "required": sorted(required_cats),
                        "active": sorted(active_cats),
                    })

            elif rule_type == "stop_loss":
                pct = params.get("pct", 0.10)
                current_return = position.get("unrealized_pnl_pct", 0.0)

                if current_return <= -pct:
                    triggered.append({
                        "rule_type": "stop_loss",
                        "threshold": -pct,
                        "current_return": round(current_return, 4),
                    })

        return {
            "should_exit": len(triggered) > 0,
            "triggered_rules": triggered,
        }

    # ── Regime Rules ─────────────────────────────────────────────────────

    @staticmethod
    def evaluate_regime(
        current_regime: str,
        regime_rules: list[dict],
    ) -> dict:
        """Determine action based on current market regime.

        Args:
            current_regime: Current regime label ("bull", "bear", "high_vol", etc.)
            regime_rules: List of RegimeAction dicts

        Returns:
            {action, sizing_override, matched_rule}
        """
        if not regime_rules:
            return {
                "action": "full_exposure",
                "sizing_override": None,
                "matched_rule": None,
            }

        for rule in regime_rules:
            if rule.get("regime", "").lower() == current_regime.lower():
                return {
                    "action": rule.get("action", "full_exposure"),
                    "sizing_override": rule.get("sizing_override"),
                    "matched_rule": rule,
                }

        # No matching regime rule → default action
        return {
            "action": "full_exposure",
            "sizing_override": None,
            "matched_rule": None,
        }
