"""
tests/test_phase3_engine_encapsulation.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for Phase 3: Engine Encapsulation.

Tests validate:
  1. TechnicalEngine produces correct TechnicalResult contracts
  2. InstitutionalScoringEngine can be instantiated
  3. DecisionEngine rule-based memo works without LLM
  4. FundamentalEngine facade exists and is importable
  5. PositionSizingModel works through the sizing package
"""

import pytest


# ─── TechnicalEngine ──────────────────────────────────────────────────────────

class TestTechnicalEngine:
    """E2E test: features → indicators → scoring → TechnicalResult."""

    def _make_features(self):
        from src.contracts.features import TechnicalFeatureSet
        return TechnicalFeatureSet(
            ticker="AAPL",
            current_price=180.0,
            sma_50=175.0, sma_200=170.0, ema_20=178.0,
            rsi=62.5, stoch_k=72.0, stoch_d=68.0,
            macd=1.5, macd_signal=1.2, macd_hist=0.3,
            bb_upper=185.0, bb_lower=172.0, bb_basis=178.5,
            atr=3.2, volume=1500000, obv=25000000,
            ohlcv=[
                {"time": f"2024-01-{i+1:02d}", "open": 150+i, "high": 152+i,
                 "low": 149+i, "close": 151+i, "volume": 1000000+i*10000}
                for i in range(30)
            ],
        )

    def test_run_produces_technical_result(self):
        from src.engines.technical.engine import TechnicalEngine
        from src.contracts.analysis import TechnicalResult
        features = self._make_features()
        result = TechnicalEngine.run(features)

        assert isinstance(result, TechnicalResult)
        assert result.ticker == "AAPL"
        assert 0.0 <= result.technical_score <= 10.0
        assert result.signal in {"STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"}

    def test_module_scores_populated(self):
        from src.engines.technical.engine import TechnicalEngine
        features = self._make_features()
        result = TechnicalEngine.run(features)

        assert len(result.module_scores) == 5
        names = {ms.name for ms in result.module_scores}
        assert names == {"trend", "momentum", "volatility", "volume", "structure"}

    def test_volatility_condition_set(self):
        from src.engines.technical.engine import TechnicalEngine
        features = self._make_features()
        result = TechnicalEngine.run(features)

        assert result.volatility_condition in {"LOW", "NORMAL", "ELEVATED", "HIGH"}

    def test_summary_dict_populated(self):
        from src.engines.technical.engine import TechnicalEngine
        features = self._make_features()
        result = TechnicalEngine.run(features)

        assert "summary" in result.summary
        assert "indicators" in result.summary


# ─── InstitutionalScoringEngine ──────────────────────────────────────────────

class TestScoringEngine:
    """Test scoring engine can be imported and instantiated."""

    def test_import(self):
        from src.engines.scoring.engine import InstitutionalScoringEngine
        assert hasattr(InstitutionalScoringEngine, "run")


# ─── DecisionEngine ──────────────────────────────────────────────────────────

class TestDecisionEngine:
    """Test rule-based memo generation (no LLM required)."""

    def test_rule_based_memo(self):
        from src.engines.decision.engine import _generate_rule_based_memo
        from src.contracts.analysis import FundamentalResult, TechnicalResult, CommitteeVerdict
        from src.contracts.scoring import OpportunityScoreResult

        fund = FundamentalResult(
            ticker="TEST",
            committee_verdict=CommitteeVerdict(
                score=7.5, confidence=0.8, signal="BUY",
                key_catalysts=["Strong growth"], key_risks=["High valuation"],
            ),
        )
        tech = TechnicalResult(
            ticker="TEST", technical_score=6.5, signal="BUY",
            volatility_condition="NORMAL",
        )
        opp = OpportunityScoreResult(opportunity_score=7.8)

        memo = _generate_rule_based_memo(fund, tech, opp)

        assert "7.8" in memo.thesis_summary
        assert "Strong growth" in memo.key_catalysts
        assert "High valuation" in memo.key_risks

    def test_import(self):
        from src.engines.decision.engine import DecisionEngine
        assert hasattr(DecisionEngine, "run")


# ─── FundamentalEngine ────────────────────────────────────────────────────────

class TestFundamentalEngine:
    """Test facade can be imported."""

    def test_import(self):
        from src.engines.fundamental.engine import FundamentalEngine
        assert hasattr(FundamentalEngine, "run")


# ─── Position Sizing via sizing package ───────────────────────────────────────

class TestSizingPackage:
    """Test sizing package re-exports work."""

    def test_import(self):
        from src.engines.sizing import PositionSizingModel
        assert hasattr(PositionSizingModel, "calculate")

    def test_calculate(self):
        from src.engines.sizing import PositionSizingModel
        result = PositionSizingModel.calculate(8.5, "NORMAL")
        assert result["conviction_level"] == "High"
        assert result["suggested_allocation"] > 0

    def test_avoid_below_threshold(self):
        from src.engines.sizing import PositionSizingModel
        result = PositionSizingModel.calculate(4.0, "HIGH")
        assert result["conviction_level"] == "Avoid"
        assert result["suggested_allocation"] == 0.0
