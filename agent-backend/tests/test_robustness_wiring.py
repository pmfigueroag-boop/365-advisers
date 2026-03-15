"""
tests/test_robustness_wiring.py
──────────────────────────────────────────────────────────────────────────────
Tests for Phase 1 Robustness: validation loop wiring, score decomposition,
and configurable weights.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════════════
#  OpportunityModel — Source Decomposition
# ═══════════════════════════════════════════════════════════════════════════════


class TestOpportunityModelDecomposition:
    """Verify that the OpportunityModel returns source_decomposition."""

    @staticmethod
    def _make_agents():
        return [
            {
                "agent": "Lynch",
                "signal": "BUY",
                "conviction": 0.7,
                "opportunity_subscores": {
                    "competitive_moat": 7.5,
                    "growth_quality": 8.0,
                },
            },
            {
                "agent": "Buffett",
                "signal": "BUY",
                "conviction": 0.6,
                "opportunity_subscores": {
                    "relative_valuation": 7.0,
                    "intrinsic_value_gap": 6.5,
                },
            },
            {
                "agent": "Marks",
                "signal": "HOLD",
                "conviction": 0.5,
                "opportunity_subscores": {"industry_structure": 5.0},
            },
            {
                "agent": "Icahn",
                "signal": "BUY",
                "conviction": 0.5,
                "opportunity_subscores": {"management_capital_allocation": 6.0},
            },
        ]

    def test_source_decomposition_present(self):
        """Output must include source_decomposition with three keys."""
        from src.engines.scoring.opportunity_model import OpportunityModel

        result = OpportunityModel.calculate(
            fundamental_metrics={
                "profitability": {"roic": 0.15, "operating_margin": 0.20},
                "valuation": {},
                "leverage": {"debt_to_equity": 0.5},
            },
            fundamental_agents=self._make_agents(),
            technical_summary={"summary": {"technical_score": 6.5, "subscores": {
                "trend": 7.0, "momentum": 6.0, "volume": 5.5,
            }}},
        )

        assert "source_decomposition" in result
        decomp = result["source_decomposition"]
        assert "quantitative_metrics" in decomp
        assert "agent_conviction" in decomp
        assert "alpha_signal_bridge" in decomp

    def test_source_decomposition_sums_to_one(self):
        """The three source percentages should approximately sum to 1.0."""
        from src.engines.scoring.opportunity_model import OpportunityModel

        result = OpportunityModel.calculate(
            fundamental_metrics={
                "profitability": {"roic": 0.12, "operating_margin": 0.18},
                "valuation": {},
                "leverage": {"debt_to_equity": 1.0},
            },
            fundamental_agents=self._make_agents(),
            technical_summary={"summary": {"technical_score": 5.0, "subscores": {
                "trend": 5.0, "momentum": 5.0, "volume": 5.0,
            }}},
        )

        decomp = result["source_decomposition"]
        total = decomp["quantitative_metrics"] + decomp["agent_conviction"] + decomp["alpha_signal_bridge"]
        assert abs(total - 1.0) < 0.01, f"Decomposition sum = {total}, expected ~1.0"

    def test_dimension_weights_present(self):
        """Output must include dimension_weights dict."""
        from src.engines.scoring.opportunity_model import OpportunityModel

        result = OpportunityModel.calculate(
            fundamental_metrics={"profitability": {}, "valuation": {}, "leverage": {}},
            fundamental_agents=[],
            technical_summary={},
        )

        assert "dimension_weights" in result
        weights = result["dimension_weights"]
        assert len(weights) == 4
        assert abs(sum(weights.values()) - 1.0) < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
#  OpportunityModel — Configurable Weights
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigurableWeights:
    """Verify that custom dimension weights change the final score."""

    def test_default_weights_equal(self):
        """Default weights should be 0.25 each."""
        from src.engines.scoring.opportunity_model import OpportunityModel

        result = OpportunityModel.calculate(
            fundamental_metrics={"profitability": {}, "valuation": {}, "leverage": {}},
            fundamental_agents=[],
            technical_summary={},
        )

        for w in result["dimension_weights"].values():
            assert abs(w - 0.25) < 0.001

    def test_custom_weights_change_score(self):
        """Skewing weights toward a strong dimension should increase the score."""
        from src.engines.scoring.opportunity_model import OpportunityModel

        base_args = dict(
            fundamental_metrics={
                "profitability": {"roic": 0.25, "operating_margin": 0.30},
                "valuation": {},
                "leverage": {"debt_to_equity": 0.3},
            },
            fundamental_agents=[],
            technical_summary={"summary": {"technical_score": 8.0, "subscores": {
                "trend": 8.5, "momentum": 8.0, "volume": 7.5,
            }}},
        )

        # Default equal weights
        result_default = OpportunityModel.calculate(**base_args)

        # Heavily weight market_behavior (where tech scores are high)
        result_skewed = OpportunityModel.calculate(
            **base_args,
            dimension_weights={
                "business_quality": 0.10,
                "valuation": 0.10,
                "financial_strength": 0.10,
                "market_behavior": 0.70,
            },
        )

        # Skewed toward strong tech should raise the overall score
        assert result_skewed["opportunity_score"] >= result_default["opportunity_score"]


# ═══════════════════════════════════════════════════════════════════════════════
#  OpportunityTracker — register_from_analysis
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegisterFromAnalysis:
    """Verify the new pipeline registration method on OpportunityTracker."""

    @patch("src.engines.opportunity_tracking.tracker.OpportunityTracker._fetch_current_price")
    @patch("src.engines.opportunity_tracking.repository.OpportunityRepository.save_opportunity")
    def test_register_creates_record(self, mock_save, mock_price):
        """register_from_analysis should call save_opportunity with correct params."""
        from src.engines.opportunity_tracking.tracker import OpportunityTracker

        mock_price.return_value = 185.50
        mock_save.return_value = 42

        tracker = OpportunityTracker()
        result = tracker.register_from_analysis(
            ticker="AAPL",
            opportunity_score=7.8,
            case_score=72.0,
            fundamental_score=7.5,
            technical_score=6.8,
        )

        assert result == 42
        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args
        # Check key fields
        assert call_kwargs.kwargs.get("ticker") or call_kwargs[1].get("ticker") == "AAPL"

    @patch("src.engines.opportunity_tracking.tracker.OpportunityTracker._fetch_current_price")
    def test_register_skips_zero_price(self, mock_price):
        """Should return None if current price is unavailable."""
        from src.engines.opportunity_tracking.tracker import OpportunityTracker

        mock_price.return_value = 0.0

        tracker = OpportunityTracker()
        result = tracker.register_from_analysis(ticker="INVALID", opportunity_score=5.0)
        assert result is None

    @patch("src.engines.opportunity_tracking.tracker.OpportunityTracker._fetch_current_price")
    @patch("src.engines.opportunity_tracking.repository.OpportunityRepository.save_opportunity")
    def test_register_derives_idea_type_alpha_strong(self, mock_save, mock_price):
        """High CASE score should classify as alpha_strong."""
        from src.engines.opportunity_tracking.tracker import OpportunityTracker

        mock_price.return_value = 100.0
        mock_save.return_value = 1

        tracker = OpportunityTracker()
        tracker.register_from_analysis(ticker="TST", case_score=85.0)

        args = mock_save.call_args
        # idea_type should be alpha_strong
        if args.kwargs:
            assert args.kwargs["idea_type"] == "alpha_strong"
        else:
            assert args[1]["idea_type"] == "alpha_strong"

    @patch("src.engines.opportunity_tracking.tracker.OpportunityTracker._fetch_current_price")
    @patch("src.engines.opportunity_tracking.repository.OpportunityRepository.save_opportunity")
    def test_register_derives_confidence(self, mock_save, mock_price):
        """Confidence should be derived from score averages."""
        from src.engines.opportunity_tracking.tracker import OpportunityTracker

        mock_price.return_value = 50.0
        mock_save.return_value = 1

        tracker = OpportunityTracker()

        # High scores → high confidence
        tracker.register_from_analysis(
            ticker="X", opportunity_score=8.0, fundamental_score=7.5, technical_score=8.0,
        )
        args = mock_save.call_args
        if args.kwargs:
            assert args.kwargs["confidence"] == "high"
        else:
            assert args[1]["confidence"] == "high"


# ═══════════════════════════════════════════════════════════════════════════════
#  Contract compatibility
# ═══════════════════════════════════════════════════════════════════════════════


class TestContractCompatibility:
    """Verify that updated contracts are backward-compatible."""

    def test_opportunity_score_result_defaults_valid(self):
        """OpportunityScoreResult should instantiate with defaults."""
        from src.contracts.scoring import OpportunityScoreResult

        result = OpportunityScoreResult()
        assert result.opportunity_score == 5.0
        assert result.source_decomposition.quantitative_metrics == 0.5
        assert result.source_decomposition.alpha_signal_bridge == 0.0
        assert len(result.dimension_weights) == 4

    def test_opportunity_score_result_serializable(self):
        """OpportunityScoreResult should serialize to dict without errors."""
        from src.contracts.scoring import OpportunityScoreResult

        result = OpportunityScoreResult(
            opportunity_score=7.5,
            dimension_weights={
                "business_quality": 0.30,
                "valuation": 0.30,
                "financial_strength": 0.20,
                "market_behavior": 0.20,
            },
        )
        data = result.model_dump()
        assert data["opportunity_score"] == 7.5
        assert data["dimension_weights"]["business_quality"] == 0.30
        assert "source_decomposition" in data
