"""
tests/test_compliance_rules_engine.py
--------------------------------------------------------------------------
Tests for the ComplianceRuleEngine (compliance_rules.py module).
"""

from __future__ import annotations

import pytest

from src.engines.compliance.compliance_rules import (
    ComplianceConfig,
    ComplianceReport,
    ComplianceRuleEngine,
    RuleResult,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

DIVERSIFIED_WEIGHTS = {
    "AAPL": 0.08, "MSFT": 0.08, "GOOGL": 0.08,
    "AMZN": 0.08, "META": 0.08, "NVDA": 0.08,
    "TSLA": 0.08, "JPM": 0.08, "V": 0.08,
    "JNJ": 0.08, "UNH": 0.08, "PG": 0.04,
}

SECTOR_MAP = {
    "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech",
    "AMZN": "Consumer", "META": "Tech", "NVDA": "Tech",
    "TSLA": "Consumer", "JPM": "Financials", "V": "Financials",
    "JNJ": "Health", "UNH": "Health", "PG": "Staples",
}

BETAS = {
    "AAPL": 1.2, "MSFT": 1.1, "GOOGL": 1.15,
    "AMZN": 1.3, "META": 1.25, "NVDA": 1.5,
    "TSLA": 1.8, "JPM": 1.1, "V": 0.9,
    "JNJ": 0.7, "UNH": 0.85, "PG": 0.6,
}


def _engine(**kw) -> ComplianceRuleEngine:
    return ComplianceRuleEngine(ComplianceConfig(**kw))


# ─── Single Position Tests ───────────────────────────────────────────────────

class TestSinglePosition:

    def test_pass(self):
        engine = _engine(max_single_position=0.10)
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS)
        rule = next(r for r in report.results if r.rule_name == "max_single_position")
        assert rule.passed

    def test_fail(self):
        weights = {"AAPL": 0.50, "MSFT": 0.50}
        engine = _engine(max_single_position=0.10)
        report = engine.check_portfolio(weights)
        rule = next(r for r in report.results if r.rule_name == "max_single_position")
        assert not rule.passed
        assert rule.severity == "violation"

    def test_custom_limit(self):
        weights = {"AAPL": 0.20, "MSFT": 0.15}
        engine = _engine(max_single_position=0.25)
        report = engine.check_portfolio(weights)
        rule = next(r for r in report.results if r.rule_name == "max_single_position")
        assert rule.passed


# ─── Sector Exposure Tests ──────────────────────────────────────────────────

class TestSectorExposure:

    def test_sector_pass(self):
        """Tech = 5×8% = 40% but default limit is 30% → fail."""
        engine = _engine()
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS, sector_map=SECTOR_MAP)
        rule = next(r for r in report.results if r.rule_name == "max_sector_exposure")
        # Tech is 40%, limit 30% → should fail
        assert not rule.passed

    def test_sector_with_high_limit(self):
        engine = _engine(max_sector_exposure=0.50)
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS, sector_map=SECTOR_MAP)
        rule = next(r for r in report.results if r.rule_name == "max_sector_exposure")
        assert rule.passed

    def test_no_sector_map_skipped(self):
        """Without sector_map, sector rule is not run."""
        engine = _engine()
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS)
        sector_rules = [r for r in report.results if r.rule_name == "max_sector_exposure"]
        assert len(sector_rules) == 0


# ─── Diversification Tests ──────────────────────────────────────────────────

class TestDiversification:

    def test_min_positions_fail(self):
        weights = {"AAPL": 0.50, "MSFT": 0.50}
        engine = _engine(min_positions=5)
        report = engine.check_portfolio(weights)
        rule = next(r for r in report.results if r.rule_name == "min_positions")
        assert not rule.passed

    def test_min_positions_pass(self):
        engine = _engine(min_positions=5)
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS)
        rule = next(r for r in report.results if r.rule_name == "min_positions")
        assert rule.passed

    def test_max_positions_pass(self):
        engine = _engine(max_positions=50)
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS)
        rule = next(r for r in report.results if r.rule_name == "max_positions")
        assert rule.passed

    def test_max_positions_fail(self):
        engine = _engine(max_positions=5)
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS)
        rule = next(r for r in report.results if r.rule_name == "max_positions")
        assert not rule.passed


# ─── Restricted Tickers ─────────────────────────────────────────────────────

class TestRestricted:

    def test_no_restricted(self):
        engine = _engine(restricted_tickers=[])
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS)
        rule = next(r for r in report.results if r.rule_name == "restricted_tickers")
        assert rule.passed

    def test_restricted_found(self):
        engine = _engine(restricted_tickers=["AAPL", "TSLA"])
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS)
        rule = next(r for r in report.results if r.rule_name == "restricted_tickers")
        assert not rule.passed
        assert rule.severity == "critical"
        assert not report.is_compliant


# ─── Beta Range ──────────────────────────────────────────────────────────────

class TestBetaRange:

    def test_beta_in_range(self):
        engine = _engine(max_portfolio_beta=1.5, min_portfolio_beta=0.5)
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS, betas=BETAS)
        rule = next(r for r in report.results if r.rule_name == "portfolio_beta_range")
        assert rule.passed

    def test_beta_too_high(self):
        # All high-beta stocks
        weights = {"NVDA": 0.5, "TSLA": 0.5}
        betas = {"NVDA": 1.5, "TSLA": 1.8}
        engine = _engine(max_portfolio_beta=1.3)
        report = engine.check_portfolio(weights, betas=betas)
        rule = next(r for r in report.results if r.rule_name == "portfolio_beta_range")
        assert not rule.passed


# ─── Turnover ────────────────────────────────────────────────────────────────

class TestTurnover:

    def test_turnover_pass(self):
        engine = _engine(max_turnover=0.50)
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS, turnover=0.30)
        rule = next(r for r in report.results if r.rule_name == "max_turnover")
        assert rule.passed

    def test_turnover_fail(self):
        engine = _engine(max_turnover=0.50)
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS, turnover=0.80)
        rule = next(r for r in report.results if r.rule_name == "max_turnover")
        assert not rule.passed
        assert rule.severity == "warning"


# ─── Full Report ─────────────────────────────────────────────────────────────

class TestFullReport:

    def test_compliant_portfolio(self):
        engine = _engine(max_single_position=0.15, min_positions=3)
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS)
        assert report.is_compliant
        assert report.violations == 0
        assert report.critical == 0

    def test_non_compliant_aggregation(self):
        engine = _engine(
            max_single_position=0.05,
            restricted_tickers=["AAPL"],
        )
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS)
        assert not report.is_compliant
        assert report.violations >= 1 or report.critical >= 1

    def test_check_type_propagated(self):
        engine = _engine()
        report = engine.check_portfolio(DIVERSIFIED_WEIGHTS, check_type="post_trade")
        assert report.check_type == "post_trade"
