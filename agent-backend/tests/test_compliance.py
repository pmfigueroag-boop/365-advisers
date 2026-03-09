"""
tests/test_compliance.py — Compliance rule engine tests.
"""
import pytest
from src.engines.compliance.models import ComplianceRule, RuleType
from src.engines.compliance.rules import ComplianceRuleEngine
from src.engines.compliance.engine import ComplianceEngine


class TestRules:
    def test_restricted_list_pass(self):
        rule = ComplianceRule(rule_id="R1", rule_type=RuleType.RESTRICTED_LIST, params={"tickers": ["XYZ"]})
        check = ComplianceRuleEngine.check_restricted_list(rule, {"AAPL": 100, "MSFT": 50})
        assert check.passed

    def test_restricted_list_fail(self):
        rule = ComplianceRule(rule_id="R1", rule_type=RuleType.RESTRICTED_LIST, params={"tickers": ["AAPL"]})
        check = ComplianceRuleEngine.check_restricted_list(rule, {"AAPL": 100})
        assert not check.passed
        assert check.severity == "critical"

    def test_position_limit_pass(self):
        rule = ComplianceRule(rule_id="PL1", rule_type=RuleType.POSITION_LIMIT, params={"max_weight": 0.10})
        check = ComplianceRuleEngine.check_position_limit(rule, {"AAPL": 0.08, "MSFT": 0.05})
        assert check.passed

    def test_position_limit_fail(self):
        rule = ComplianceRule(rule_id="PL1", rule_type=RuleType.POSITION_LIMIT, params={"max_weight": 0.10})
        check = ComplianceRuleEngine.check_position_limit(rule, {"AAPL": 0.15})
        assert not check.passed

    def test_sector_limit(self):
        rule = ComplianceRule(rule_id="SL1", rule_type=RuleType.SECTOR_LIMIT, params={"max_sector_weight": 0.30})
        check = ComplianceRuleEngine.check_sector_limit(rule, {"Tech": 0.35})
        assert not check.passed

    def test_concentration_hhi(self):
        rule = ComplianceRule(rule_id="CC1", rule_type=RuleType.CONCENTRATION, params={"max_hhi": 0.10})
        check = ComplianceRuleEngine.check_concentration(rule, {"A": 0.5, "B": 0.5})  # HHI = 0.50
        assert not check.passed

    def test_concentration_diversified(self):
        rule = ComplianceRule(rule_id="CC1", rule_type=RuleType.CONCENTRATION, params={"max_hhi": 0.30})
        check = ComplianceRuleEngine.check_concentration(rule, {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25})  # HHI = 0.25
        assert check.passed

    def test_leverage(self):
        rule = ComplianceRule(rule_id="LV1", rule_type=RuleType.LEVERAGE, params={"max_leverage": 2.0})
        check = ComplianceRuleEngine.check_leverage(rule, 2.5)
        assert not check.passed
        assert check.severity == "critical"

    def test_trade_frequency(self):
        rule = ComplianceRule(rule_id="TF1", rule_type=RuleType.TRADE_FREQUENCY, params={"max_daily_trades": 50})
        check = ComplianceRuleEngine.check_trade_frequency(rule, 60)
        assert not check.passed

    def test_holding_period(self):
        rule = ComplianceRule(rule_id="HP1", rule_type=RuleType.HOLDING_PERIOD, params={"min_holding_days": 3})
        trades = [{"ticker": "AAPL", "holding_days": 1}]
        check = ComplianceRuleEngine.check_holding_period(rule, trades)
        assert not check.passed


class TestComplianceEngine:
    def test_default_rules(self):
        engine = ComplianceEngine()
        assert len(engine.rules) == 7

    def test_run_all_compliant(self):
        engine = ComplianceEngine()
        report = engine.run_all(
            weights={"AAPL": 0.05, "MSFT": 0.05, "GOOGL": 0.05, "AMZN": 0.05},
            positions={"AAPL": 100},
            sector_weights={"Tech": 0.20},
            gross_exposure=1.0,
            trades_today=5,
        )
        assert report.is_compliant
        assert report.critical == 0

    def test_run_all_non_compliant(self):
        engine = ComplianceEngine()
        engine.add_rule(ComplianceRule(
            rule_id="R-TEST", rule_type=RuleType.RESTRICTED_LIST,
            params={"tickers": ["AAPL"]},
        ))
        report = engine.run_all(positions={"AAPL": 100})
        assert not report.is_compliant
        assert report.critical > 0

    def test_add_remove_rule(self):
        engine = ComplianceEngine()
        initial = len(engine.rules)
        engine.add_rule(ComplianceRule(rule_id="NEW", rule_type=RuleType.POSITION_LIMIT))
        assert len(engine.rules) == initial + 1
        engine.remove_rule("NEW")
        assert len(engine.rules) == initial
