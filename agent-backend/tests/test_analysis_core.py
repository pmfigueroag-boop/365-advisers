"""
tests/test_analysis_core.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for the ANALYSIS module's core business logic:
  - DecisionMatrix (investment position classification)
  - OpportunityModel (12-factor institutional scoring)
  - PositionSizingModel (allocation calculation)

These are the deterministic components that produce the investment
recommendations shown to users — zero tolerance for regressions.
"""

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DECISION MATRIX
# ═══════════════════════════════════════════════════════════════════════════════


class TestDecisionMatrix:

    def test_strong_opportunity(self):
        """fund ≥ 8.0, tech ≥ 7.0 → Strong Opportunity"""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(9.0, 8.0) == "Strong Opportunity"
        assert DecisionMatrix.determine_position(8.0, 7.0) == "Strong Opportunity"

    def test_moderate_high_fund_mid_tech(self):
        """fund ≥ 8.0, 4.0 ≤ tech < 7.0 → Moderate Opportunity"""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(8.5, 5.0) == "Moderate Opportunity"
        assert DecisionMatrix.determine_position(8.0, 4.0) == "Moderate Opportunity"

    def test_moderate_good_fund_great_tech(self):
        """fund 6.0-7.9, tech ≥ 7.0 → Moderate Opportunity"""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(6.5, 8.0) == "Moderate Opportunity"

    def test_moderate_good_fund_ok_tech(self):
        """fund 6.0-7.9, tech 5.0-6.9 → Moderate Opportunity"""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(7.0, 5.0) == "Moderate Opportunity"
        assert DecisionMatrix.determine_position(6.0, 6.0) == "Moderate Opportunity"

    def test_caution_great_fund_poor_tech(self):
        """fund ≥ 8.0, tech < 4.0 → Caution (wait for entry)"""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(9.0, 2.0) == "Caution"

    def test_neutral_mid_mid(self):
        """fund 4.0-5.9, tech 4.0-6.9 → Neutral"""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(5.0, 5.0) == "Neutral"
        assert DecisionMatrix.determine_position(4.0, 4.0) == "Neutral"

    def test_caution_value_trap(self):
        """fund < 5.0, tech ≥ 7.0 → Caution (value trap)"""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(3.0, 8.0) == "Caution"

    def test_avoid_low_low(self):
        """fund < 4.0, tech < 4.0 → Avoid"""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(2.0, 2.0) == "Avoid"

    def test_avoid_mid_fund_low_tech(self):
        """fund 4.0-5.9, tech < 4.0 → Avoid"""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(4.0, 3.0) == "Avoid"

    def test_confidence_no_divergence(self):
        """When fund == tech, no penalty applied."""
        from src.engines.decision.classifier import DecisionMatrix
        conf = DecisionMatrix.calculate_confidence(0.8, 7.0, 7.0)
        assert conf == 0.8

    def test_confidence_high_divergence(self):
        """Max divergence (10) → 30% penalty."""
        from src.engines.decision.classifier import DecisionMatrix
        conf = DecisionMatrix.calculate_confidence(1.0, 10.0, 0.0)
        assert conf == 0.7

    def test_confidence_clamps_to_zero(self):
        """Confidence never goes negative."""
        from src.engines.decision.classifier import DecisionMatrix
        conf = DecisionMatrix.calculate_confidence(0.1, 10.0, 0.0)
        assert conf >= 0.0

    def test_analyze_returns_full_dict(self):
        """Verify the complete output structure."""
        from src.engines.decision.classifier import DecisionMatrix
        result = DecisionMatrix.analyze(7.0, 6.0, 0.75)
        assert "investment_position" in result
        assert "confidence_score" in result
        assert "fundamental_aggregate" in result
        assert "technical_aggregate" in result
        assert result["fundamental_aggregate"] == 7.0
        assert result["technical_aggregate"] == 6.0

    def test_boundary_exact_8_7(self):
        """Exact boundary values: fund=8.0, tech=7.0 → Strong."""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(8.0, 7.0) == "Strong Opportunity"

    def test_boundary_just_below_strong(self):
        """Just below strong boundary → Moderate."""
        from src.engines.decision.classifier import DecisionMatrix
        assert DecisionMatrix.determine_position(7.9, 7.0) == "Moderate Opportunity"
        assert DecisionMatrix.determine_position(8.0, 6.9) == "Moderate Opportunity"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. OPPORTUNITY MODEL
# ═══════════════════════════════════════════════════════════════════════════════


class TestOpportunityModel:

    def test_neutral_when_no_data(self):
        """Empty inputs → neutral score around 5.0."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=[],
            technical_summary={},
        )
        assert 4.0 <= result["opportunity_score"] <= 6.0

    def test_bullish_agents_raise_score(self):
        """4 BUY agents with high conviction → score > 6."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        agents = [
            {"agent": "Value & Margin of Safety", "signal": "BUY", "conviction": 0.9},
            {"agent": "Quality & Moat", "signal": "BUY", "conviction": 0.85},
            {"agent": "Capital Allocation", "signal": "BUY", "conviction": 0.8},
            {"agent": "Risk & Macro Stress", "signal": "BUY", "conviction": 0.75},
        ]
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=agents,
            technical_summary={"technical_score": 8.0},
        )
        assert result["opportunity_score"] > 6.0

    def test_bearish_agents_lower_score(self):
        """4 SELL agents → score < 5."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        agents = [
            {"agent": "Value & Margin of Safety", "signal": "SELL", "conviction": 0.9},
            {"agent": "Quality & Moat", "signal": "SELL", "conviction": 0.85},
            {"agent": "Capital Allocation", "signal": "SELL", "conviction": 0.8},
            {"agent": "Risk & Macro Stress", "signal": "SELL", "conviction": 0.75},
        ]
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=agents,
            technical_summary={"technical_score": 2.0},
        )
        assert result["opportunity_score"] < 5.0

    def test_agent_name_mapping_graph_names(self):
        """Verify that graph agent names are correctly mapped (Phase 1A fix)."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        agents = [
            {"agent": "Value & Margin of Safety", "signal": "BUY", "conviction": 0.9},
        ]
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=agents,
            technical_summary={},
        )
        # If the mapping works, Buffett's factors should differ from neutral 5.0
        assert result["factors"]["relative_valuation"] != 5.0
        assert result["factors"]["intrinsic_value_gap"] != 5.0

    def test_agent_name_mapping_legacy_names(self):
        """Verify backward compatibility with legacy agent names."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        agents = [
            {"agent_name": "Lynch", "confidence": 0.8, "signal": "BUY"},
        ]
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=agents,
            technical_summary={},
        )
        # Lynch maps to competitive_moat and growth_quality
        assert result["factors"]["competitive_moat"] != 5.0

    def test_factors_count(self):
        """Exactly 12 factors should be returned."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=[],
            technical_summary={},
        )
        assert len(result["factors"]) == 12

    def test_dimensions_count(self):
        """Exactly 4 dimensions should be returned."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=[],
            technical_summary={},
        )
        assert len(result["dimensions"]) == 4
        for dim_name in ["business_quality", "valuation", "financial_strength", "market_behavior"]:
            assert dim_name in result["dimensions"]

    def test_score_bounds(self):
        """Score should always be between 0 and 10."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        # Extreme bullish
        agents_bull = [
            {"agent": "Value & Margin of Safety", "signal": "BUY", "conviction": 1.0},
            {"agent": "Quality & Moat", "signal": "BUY", "conviction": 1.0},
            {"agent": "Capital Allocation", "signal": "BUY", "conviction": 1.0},
            {"agent": "Risk & Macro Stress", "signal": "BUY", "conviction": 1.0},
        ]
        result_bull = OpportunityModel.calculate(
            fundamental_metrics={"profitability": {"roic": 0.5}},
            fundamental_agents=agents_bull,
            technical_summary={"technical_score": 10.0},
        )
        assert 0.0 <= result_bull["opportunity_score"] <= 10.0

        # Extreme bearish
        agents_bear = [
            {"agent": "Value & Margin of Safety", "signal": "SELL", "conviction": 1.0},
            {"agent": "Quality & Moat", "signal": "SELL", "conviction": 1.0},
            {"agent": "Capital Allocation", "signal": "SELL", "conviction": 1.0},
            {"agent": "Risk & Macro Stress", "signal": "SELL", "conviction": 1.0},
        ]
        result_bear = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=agents_bear,
            technical_summary={"technical_score": 0.0},
        )
        assert 0.0 <= result_bear["opportunity_score"] <= 10.0

    def test_recorded_at_present(self):
        """Result should include an ISO timestamp."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=[],
            technical_summary={},
        )
        assert "recorded_at" in result
        assert "T" in result["recorded_at"]  # ISO format contains 'T'

    def test_market_behavior_uses_real_subscores(self):
        """Market Behavior factors should use distinct module subscores, not duplicate tech_score."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=[],
            technical_summary={
                "summary": {
                    "technical_score": 6.0,
                    "subscores": {
                        "trend": 9.0,
                        "momentum": 3.0,
                        "volume": 7.0,
                    },
                },
            },
        )
        assert result["factors"]["trend_strength"] == 9.0
        assert result["factors"]["momentum"] == 3.0
        assert result["factors"]["institutional_flow"] == 7.0
        # And they should NOT all be the same
        assert not (result["factors"]["trend_strength"] == result["factors"]["momentum"] == result["factors"]["institutional_flow"])

    def test_market_behavior_fallback_to_tech_score(self):
        """Without subscores, Market Behavior should fall back to tech_score."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        result = OpportunityModel.calculate(
            fundamental_metrics={},
            fundamental_agents=[],
            technical_summary={"technical_score": 7.5},
        )
        assert result["factors"]["trend_strength"] == 7.5
        assert result["factors"]["momentum"] == 7.5
        assert result["factors"]["institutional_flow"] == 7.5

    def test_balance_sheet_uses_debt_equity(self):
        """Balance Sheet factor should use debt/equity when available."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        # Zero debt → score 10
        result_no_debt = OpportunityModel.calculate(
            fundamental_metrics={"leverage": {"debt_to_equity": 0.0}},
            fundamental_agents=[],
            technical_summary={},
        )
        assert result_no_debt["factors"]["balance_sheet_strength"] == 10.0

        # Heavy debt (D/E = 3.0) → score 0
        result_heavy = OpportunityModel.calculate(
            fundamental_metrics={"leverage": {"debt_to_equity": 3.0}},
            fundamental_agents=[],
            technical_summary={},
        )
        assert result_heavy["factors"]["balance_sheet_strength"] == 0.0

        # Moderate debt (D/E = 1.0) → ~6.67
        result_mod = OpportunityModel.calculate(
            fundamental_metrics={"leverage": {"debt_to_equity": 1.0}},
            fundamental_agents=[],
            technical_summary={},
        )
        assert 6.0 <= result_mod["factors"]["balance_sheet_strength"] <= 7.0

    def test_earnings_stability_uses_operating_margin(self):
        """Earnings Stability should use operating margin when available."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        # 30% margin → score 10
        result_high = OpportunityModel.calculate(
            fundamental_metrics={"profitability": {"operating_margin": 0.30}},
            fundamental_agents=[],
            technical_summary={},
        )
        assert result_high["factors"]["earnings_stability"] == 10.0

        # 15% margin → score 5
        result_mid = OpportunityModel.calculate(
            fundamental_metrics={"profitability": {"operating_margin": 0.15}},
            fundamental_agents=[],
            technical_summary={},
        )
        assert result_mid["factors"]["earnings_stability"] == 5.0

    def test_fcf_yield_capped(self):
        """FCF yield score should never exceed 10."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        result = OpportunityModel.calculate(
            fundamental_metrics={"profitability": {"roic": 0.50}},  # 50% ROIC
            fundamental_agents=[],
            technical_summary={},
        )
        assert result["factors"]["fcf_yield"] <= 10.0

    def test_negative_operating_margin_floors_at_zero(self):
        """Negative op margin → earnings_stability floors at 0."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        result = OpportunityModel.calculate(
            fundamental_metrics={"profitability": {"operating_margin": -0.10}},
            fundamental_agents=[],
            technical_summary={},
        )
        assert result["factors"]["earnings_stability"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. POSITION SIZING MODEL
# ═══════════════════════════════════════════════════════════════════════════════


class TestPositionSizingModel:

    def test_very_high_conviction(self):
        """Score ≥ 9.0 → 'Very High' conviction, base 10%."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(9.5, "LOW")
        assert result["conviction_level"] == "Very High"
        assert result["base_position_size"] == 10.0

    def test_high_conviction(self):
        """Score 8.0-8.9 → 'High' conviction, base 6.5%."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(8.5, "LOW")
        assert result["conviction_level"] == "High"
        assert result["base_position_size"] == 6.5

    def test_moderate_conviction(self):
        """Score 7.0-7.9 → 'Moderate' conviction, base 3.5%."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(7.0, "LOW")
        assert result["conviction_level"] == "Moderate"
        assert result["base_position_size"] == 3.5

    def test_watch_conviction(self):
        """Score 6.0-6.9 → 'Watch' conviction, base 1.5%."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(6.0, "LOW")
        assert result["conviction_level"] == "Watch"
        assert result["base_position_size"] == 1.5

    def test_avoid_zero_allocation(self):
        """Score < 6 → 0% allocation."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(4.0, "LOW")
        assert result["conviction_level"] == "Avoid"
        assert result["suggested_allocation"] == 0.0

    def test_low_risk_no_adjustment(self):
        """Risk 'LOW' → multiplier 1.0 (no reduction)."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(9.0, "LOW")
        assert result["risk_adjustment"] == 1.0
        assert result["suggested_allocation"] == 10.0

    def test_normal_risk_adjustment(self):
        """Risk 'NORMAL' → multiplier 0.75."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(9.0, "NORMAL")
        assert result["risk_adjustment"] == 0.75
        assert result["suggested_allocation"] == 7.5

    def test_elevated_risk_adjustment(self):
        """Risk 'ELEVATED' → multiplier 0.50."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(9.0, "ELEVATED")
        assert result["risk_adjustment"] == 0.50
        assert result["suggested_allocation"] == 5.0

    def test_high_risk_heavy_cut(self):
        """Risk 'HIGH' → multiplier 0.25."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(9.0, "HIGH")
        assert result["risk_adjustment"] == 0.25
        assert result["suggested_allocation"] == 2.5

    def test_max_position_cap(self):
        """Allocation should never exceed 10%."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(9.5, "LOW")
        assert result["suggested_allocation"] <= 10.0

    def test_action_increase(self):
        """Allocation ≥ 6% → 'Increase Position'."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(8.5, "LOW")
        assert result["recommended_action"] == "Increase Position"

    def test_action_maintain(self):
        """Allocation 3-5.9% → 'Maintain Position'."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(7.5, "LOW")
        assert result["recommended_action"] == "Maintain Position"

    def test_action_reduce(self):
        """Allocation 0.1-2.9% → 'Reduce Position'."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(9.0, "HIGH")
        assert result["recommended_action"] == "Reduce Position"

    def test_action_exit(self):
        """Allocation 0% → 'Exit Position'."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(4.0, "HIGH")
        assert result["recommended_action"] == "Exit Position"

    def test_unknown_risk_defaults_medium(self):
        """Unknown risk string → default multiplier 0.75."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(9.0, "UNKNOWN")
        assert result["risk_adjustment"] == 0.75
        assert result["risk_level"] == "Medium"

    def test_output_keys(self):
        """Verify all expected keys are present."""
        from src.engines.portfolio.position_sizing import PositionSizingModel
        result = PositionSizingModel.calculate(7.0, "NORMAL")
        expected_keys = {
            "opportunity_score", "conviction_level", "risk_level",
            "base_position_size", "risk_adjustment", "suggested_allocation",
            "recommended_action",
        }
        assert set(result.keys()) == expected_keys
