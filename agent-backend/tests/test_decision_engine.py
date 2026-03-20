"""
tests/test_decision_engine.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Decision Engine — DecisionMatrix classifier, confidence
calculation, and rule-based CIO memo generation.

All tests use mock data and require no LLM or external API calls.
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from src.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _mock_google_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")


# ── DecisionMatrix.determine_position ─────────────────────────────────────────


class TestDecisionMatrixPosition:
    """Test the non-linear position classification matrix."""

    def test_strong_buy_high_fund_high_tech(self):
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(9.0, 8.0) == "STRONG BUY"

    def test_strong_buy_boundary(self):
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(8.0, 7.0) == "STRONG BUY"

    def test_buy_high_fund_moderate_tech(self):
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(8.5, 5.0) == "BUY"

    def test_buy_moderate_fund_good_tech(self):
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(6.5, 6.0) == "BUY"

    def test_hold_mid_range(self):
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(5.0, 5.0) == "HOLD"

    def test_sell_good_fund_weak_tech(self):
        """Good fundamentals but awful technicals = wait for entry."""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(8.0, 2.0) == "SELL"

    def test_sell_weak_fund_strong_tech(self):
        """Weak fundamentals + strong momentum = value trap / speculative."""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(3.0, 8.0) == "SELL"

    def test_strong_sell_both_weak(self):
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(3.0, 3.0) == "STRONG SELL"

    def test_strong_sell_boundary(self):
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(4.0, 3.0) == "STRONG SELL"

    def test_hold_neutral_zone(self):
        from src.engines.decision.classifier import DecisionMatrix
        result = DecisionMatrix.determine_position(6.0, 4.0)
        assert result == "HOLD"


# ── DecisionMatrix.calculate_confidence ───────────────────────────────────────


class TestDecisionMatrixConfidence:
    """Test confidence adjustment based on fundamental-technical divergence."""

    def test_no_divergence_preserves_confidence(self):
        from src.engines.decision.classifier import DecisionMatrix
        conf = DecisionMatrix.calculate_confidence(0.80, 7.0, 7.0)
        assert conf == 0.80  # No penalty when scores align

    def test_max_divergence_applies_30pct_penalty(self):
        from src.engines.decision.classifier import DecisionMatrix
        conf = DecisionMatrix.calculate_confidence(1.0, 10.0, 0.0)
        assert conf == 0.70  # 30% penalty at max divergence

    def test_moderate_divergence_partial_penalty(self):
        from src.engines.decision.classifier import DecisionMatrix
        conf = DecisionMatrix.calculate_confidence(0.80, 8.0, 4.0)
        # divergence=4, penalty = 4/10 * 0.30 = 0.12
        # final = 0.80 * (1 - 0.12) = 0.704
        assert conf == 0.70

    def test_confidence_clamped_at_zero(self):
        from src.engines.decision.classifier import DecisionMatrix
        conf = DecisionMatrix.calculate_confidence(0.10, 10.0, 0.0)
        assert conf >= 0.0

    def test_confidence_clamped_at_one(self):
        from src.engines.decision.classifier import DecisionMatrix
        conf = DecisionMatrix.calculate_confidence(1.0, 5.0, 5.0)
        assert conf <= 1.0


# ── DecisionMatrix.analyze ────────────────────────────────────────────────────


class TestDecisionMatrixAnalyze:
    """Test the unified analyze() method returns all expected keys."""

    def test_analyze_returns_complete_dict(self):
        from src.engines.decision.classifier import DecisionMatrix
        result = DecisionMatrix.analyze(7.5, 6.0, 0.75)
        assert "investment_position" in result
        assert "confidence_score" in result
        assert "fundamental_aggregate" in result
        assert "technical_aggregate" in result
        assert result["fundamental_aggregate"] == 7.5
        assert result["technical_aggregate"] == 6.0

    def test_analyze_strong_buy_scenario(self):
        from src.engines.decision.classifier import DecisionMatrix
        result = DecisionMatrix.analyze(9.0, 8.0, 0.90)
        assert result["investment_position"] == "STRONG BUY"
        assert result["confidence_score"] > 0.80  # Low divergence


# ── Rule-Based CIO Memo ──────────────────────────────────────────────────────


class TestRuleBasedMemo:
    """Test the deterministic fallback memo generator."""

    def _make_fundamental(self, score=7.0, signal="BUY"):
        from src.contracts.analysis import FundamentalResult, CommitteeVerdict
        return FundamentalResult(
            ticker="TEST",
            committee_verdict=CommitteeVerdict(
                signal=signal,
                score=score,
                confidence=0.75,
                consensus_narrative="Test narrative",
                key_catalysts=["catalyst1", "catalyst2"],
                key_risks=["risk1", "risk2"],
            ),
        )

    def _make_technical(self, score=6.5, signal="BUY"):
        from src.contracts.analysis import TechnicalResult
        return TechnicalResult(
            ticker="TEST",
            technical_score=score,
            signal=signal,
            volatility_condition="NORMAL",
        )

    def _make_opportunity(self, score=7.0):
        from src.contracts.scoring import OpportunityScoreResult, DimensionScores
        return OpportunityScoreResult(
            opportunity_score=score,
            dimensions=DimensionScores(),
            grade="A",
            recommendation="BUY",
        )

    def test_strong_opportunity_thesis(self):
        from src.engines.decision.engine import _generate_rule_based_memo
        memo = _generate_rule_based_memo(
            self._make_fundamental(8.0),
            self._make_technical(7.5),
            self._make_opportunity(8.0),
        )
        assert "Strong investment opportunity" in memo.thesis_summary

    def test_moderate_opportunity_thesis(self):
        from src.engines.decision.engine import _generate_rule_based_memo
        memo = _generate_rule_based_memo(
            self._make_fundamental(6.0),
            self._make_technical(5.5),
            self._make_opportunity(6.0),
        )
        assert "Moderate opportunity" in memo.thesis_summary

    def test_below_average_opportunity_thesis(self):
        from src.engines.decision.engine import _generate_rule_based_memo
        memo = _generate_rule_based_memo(
            self._make_fundamental(3.0, "SELL"),
            self._make_technical(3.0, "SELL"),
            self._make_opportunity(3.5),
        )
        assert "Below-average" in memo.thesis_summary

    def test_memo_includes_catalysts_and_risks(self):
        from src.engines.decision.engine import _generate_rule_based_memo
        memo = _generate_rule_based_memo(
            self._make_fundamental(),
            self._make_technical(),
            self._make_opportunity(),
        )
        assert len(memo.key_catalysts) >= 1
        assert len(memo.key_risks) >= 1

    def test_memo_valuation_view_has_score(self):
        from src.engines.decision.engine import _generate_rule_based_memo
        memo = _generate_rule_based_memo(
            self._make_fundamental(7.5),
            self._make_technical(6.0),
            self._make_opportunity(7.0),
        )
        assert "7.5" in memo.valuation_view
        assert "6.0" in memo.technical_context
