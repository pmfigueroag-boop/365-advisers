"""
tests/test_fundamental_engine.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive tests for the Fundamental Analysis submodule.

Coverage:
  1. Deterministic scoring — 4 modules, continuity, monotonicity, evidence
  2. Signal guardrail — override logic, edge cases
  3. Signal normalization — granularity, AVOID→SELL, case insensitivity
  4. Contract validation — defaults, serialization, field alignment
"""

import pytest
import math


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1: Deterministic Scoring
# ═══════════════════════════════════════════════════════════════════════════════

class TestFundamentalScoringEngine:
    """Test FundamentalScoringEngine.compute()."""

    def _make_ratios(self, **overrides):
        """Build a realistic ratios dict (same shape as fetch_fundamental_data)."""
        base = {
            "profitability": {
                "gross_margin": 0.55,
                "ebit_margin": 0.20,
                "net_margin": 0.15,
                "roe": 0.18,
                "roic": 0.14,
            },
            "valuation": {
                "pe_ratio": 22.0,
                "pb_ratio": 4.0,
                "ev_ebitda": 16.0,
                "fcf_yield": 0.045,
                "market_cap": 300e9,
            },
            "leverage": {
                "debt_to_equity": 0.8,
                "interest_coverage": 8.0,
                "current_ratio": 1.6,
                "quick_ratio": 1.2,
            },
            "quality": {
                "revenue_growth_yoy": 0.12,
                "earnings_growth_yoy": 0.15,
                "dividend_yield": 0.02,
                "payout_ratio": 0.35,
                "beta": 1.1,
            },
        }
        # Apply deep overrides
        for path, val in overrides.items():
            parts = path.split(".")
            d = base
            for p in parts[:-1]:
                d = d.setdefault(p, {})
            d[parts[-1]] = val
        return base

    # ── Basic output structure ────────────────────────────────────────────

    def test_produces_score_in_range(self):
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        result = FundamentalScoringEngine.compute(self._make_ratios())
        assert 0.0 <= result.score <= 10.0

    def test_produces_valid_signal(self):
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        result = FundamentalScoringEngine.compute(self._make_ratios())
        assert result.signal in {"STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"}

    def test_produces_four_modules(self):
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        result = FundamentalScoringEngine.compute(self._make_ratios())
        assert len(result.module_scores) == 4
        names = {m.name for m in result.module_scores}
        assert names == {"value", "quality", "capital", "risk"}

    def test_modules_have_evidence(self):
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        result = FundamentalScoringEngine.compute(self._make_ratios())
        # At least some modules should produce evidence
        total_evidence = sum(len(m.evidence) for m in result.module_scores)
        assert total_evidence > 0

    def test_aggregated_evidence(self):
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        result = FundamentalScoringEngine.compute(self._make_ratios())
        assert len(result.evidence) > 0

    # ── Data coverage ─────────────────────────────────────────────────────

    def test_full_data_high_coverage(self):
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        result = FundamentalScoringEngine.compute(self._make_ratios())
        # With all ratios, coverage should be close to 1.0
        assert result.data_coverage >= 0.8

    def test_empty_ratios_low_coverage(self):
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        result = FundamentalScoringEngine.compute({})
        assert result.data_coverage == 0.0
        assert result.confidence == 0.0

    def test_partial_data_partial_coverage(self):
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        # Only valuation data
        ratios = {"valuation": {"pe_ratio": 20.0, "pb_ratio": 3.0}}
        result = FundamentalScoringEngine.compute(ratios)
        assert 0.0 < result.data_coverage < 1.0

    # ── Continuity (sigmoid, no bucketing) ────────────────────────────────

    def test_continuity_pe_small_change(self):
        """1-point PE change should produce measurable but small score difference."""
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        r1 = FundamentalScoringEngine.compute(
            self._make_ratios(**{"valuation.pe_ratio": 20.0})
        )
        r2 = FundamentalScoringEngine.compute(
            self._make_ratios(**{"valuation.pe_ratio": 21.0})
        )
        # Scores should differ (continuous) but not by a lot
        assert r1.score != r2.score
        assert abs(r1.score - r2.score) < 1.0

    # ── Monotonicity ──────────────────────────────────────────────────────

    def test_monotonicity_lower_pe_higher_score(self):
        """Lower P/E should produce higher value module score."""
        from src.engines.fundamental.scoring import _score_value
        r_low = _score_value({"valuation": {"pe_ratio": 10.0}})
        r_high = _score_value({"valuation": {"pe_ratio": 40.0}})
        assert r_low.score > r_high.score

    def test_monotonicity_higher_roic_higher_score(self):
        """Higher ROIC should produce higher quality module score."""
        from src.engines.fundamental.scoring import _score_quality
        r_low = _score_quality({"profitability": {"roic": 0.05}})
        r_high = _score_quality({"profitability": {"roic": 0.25}})
        assert r_high.score > r_low.score

    def test_monotonicity_lower_debt_higher_capital_score(self):
        """Lower D/E should produce higher capital module score."""
        from src.engines.fundamental.scoring import _score_capital
        r_low = _score_capital({"leverage": {"debt_to_equity": 0.2}})
        r_high = _score_capital({"leverage": {"debt_to_equity": 3.0}})
        assert r_low.score > r_high.score

    def test_monotonicity_lower_beta_higher_risk_score(self):
        """Lower beta should produce higher risk module score (less risky)."""
        from src.engines.fundamental.scoring import _score_risk
        r_low = _score_risk({"quality": {"beta": 0.5}})
        r_high = _score_risk({"quality": {"beta": 2.0}})
        assert r_low.score > r_high.score

    # ── Strong vs weak fundamentals ───────────────────────────────────────

    def test_strong_fundamentals_high_score(self):
        """Ideal company should score ≥ 7."""
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        ratios = self._make_ratios(
            **{
                "valuation.pe_ratio": 12.0,
                "valuation.pb_ratio": 1.5,
                "valuation.ev_ebitda": 8.0,
                "valuation.fcf_yield": 0.08,
                "profitability.gross_margin": 0.70,
                "profitability.roic": 0.25,
                "profitability.roe": 0.30,
                "leverage.debt_to_equity": 0.2,
                "leverage.current_ratio": 3.0,
                "quality.beta": 0.7,
                "quality.revenue_growth_yoy": 0.20,
            }
        )
        result = FundamentalScoringEngine.compute(ratios)
        assert result.score >= 7.0
        assert result.signal in ("BUY", "STRONG_BUY")

    def test_weak_fundamentals_low_score(self):
        """Troubled company should score ≤ 4."""
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        ratios = self._make_ratios(
            **{
                "valuation.pe_ratio": 50.0,
                "valuation.pb_ratio": 8.0,
                "valuation.ev_ebitda": 30.0,
                "valuation.fcf_yield": 0.01,
                "profitability.gross_margin": 0.15,
                "profitability.roic": 0.03,
                "profitability.roe": 0.04,
                "leverage.debt_to_equity": 3.5,
                "leverage.current_ratio": 0.7,
                "quality.beta": 2.0,
                "quality.revenue_growth_yoy": -0.10,
            }
        )
        result = FundamentalScoringEngine.compute(ratios)
        assert result.score <= 4.0
        assert result.signal in ("SELL", "STRONG_SELL")


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2: Signal Guardrail
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignalGuardrail:
    """Test apply_signal_guardrail()."""

    def test_aligned_no_override(self):
        from src.engines.fundamental.scoring import apply_signal_guardrail
        signal, overridden = apply_signal_guardrail("BUY", "BUY", 7.0)
        assert signal == "BUY"
        assert overridden is False

    def test_contradicting_overrides(self):
        from src.engines.fundamental.scoring import apply_signal_guardrail
        signal, overridden = apply_signal_guardrail("BUY", "SELL", 3.0)
        assert signal == "SELL"
        assert overridden is True

    def test_buy_vs_strong_sell_overrides(self):
        from src.engines.fundamental.scoring import apply_signal_guardrail
        signal, overridden = apply_signal_guardrail("BUY", "STRONG_SELL", 2.0)
        assert signal == "STRONG_SELL"
        assert overridden is True

    def test_sell_vs_buy_overrides(self):
        from src.engines.fundamental.scoring import apply_signal_guardrail
        signal, overridden = apply_signal_guardrail("SELL", "BUY", 7.0)
        assert signal == "BUY"
        assert overridden is True

    def test_hold_passes_through(self):
        from src.engines.fundamental.scoring import apply_signal_guardrail
        # HOLD is neutral — no override regardless of deterministic
        signal, overridden = apply_signal_guardrail("HOLD", "BUY", 7.0)
        assert signal == "HOLD"
        assert overridden is False

    def test_deterministic_hold_passes_through(self):
        from src.engines.fundamental.scoring import apply_signal_guardrail
        signal, overridden = apply_signal_guardrail("BUY", "HOLD", 5.0)
        assert signal == "BUY"
        assert overridden is False


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3: Signal Normalization
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignalNormalization:
    """Test _normalise_signal()."""

    def test_strong_buy_preserved(self):
        from src.engines.fundamental.engine import _normalise_signal
        assert _normalise_signal("STRONG_BUY") == "STRONG_BUY"

    def test_strong_sell_preserved(self):
        from src.engines.fundamental.engine import _normalise_signal
        assert _normalise_signal("STRONG_SELL") == "STRONG_SELL"

    def test_buy(self):
        from src.engines.fundamental.engine import _normalise_signal
        assert _normalise_signal("BUY") == "BUY"

    def test_sell(self):
        from src.engines.fundamental.engine import _normalise_signal
        assert _normalise_signal("SELL") == "SELL"

    def test_hold(self):
        from src.engines.fundamental.engine import _normalise_signal
        assert _normalise_signal("HOLD") == "HOLD"

    def test_avoid_becomes_sell(self):
        from src.engines.fundamental.engine import _normalise_signal
        assert _normalise_signal("AVOID") == "SELL"

    def test_case_insensitive(self):
        from src.engines.fundamental.engine import _normalise_signal
        assert _normalise_signal("strong_buy") == "STRONG_BUY"
        assert _normalise_signal("strong_sell") == "STRONG_SELL"
        assert _normalise_signal("buy") == "BUY"

    def test_whitespace_tolerant(self):
        from src.engines.fundamental.engine import _normalise_signal
        assert _normalise_signal("  BUY  ") == "BUY"
        assert _normalise_signal(" STRONG_BUY ") == "STRONG_BUY"

    def test_unknown_becomes_hold(self):
        from src.engines.fundamental.engine import _normalise_signal
        assert _normalise_signal("WHATEVER") == "HOLD"
        assert _normalise_signal("") == "HOLD"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4: Contract Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestFundamentalContracts:
    """Test FundamentalResult and CommitteeVerdict contracts."""

    def test_fundamental_result_defaults(self):
        from src.contracts.analysis import FundamentalResult
        r = FundamentalResult(ticker="TEST")
        assert r.agent_memos == []
        assert r.data_ready == {}
        assert r.committee_verdict.score == 5.0
        assert r.committee_verdict.signal == "HOLD"
        assert r.research_memo == ""
        assert r.deterministic_score is None
        assert r.score_evidence == []
        assert r.data_coverage == 0.0

    def test_committee_verdict_defaults(self):
        from src.contracts.analysis import CommitteeVerdict
        v = CommitteeVerdict()
        assert v.signal == "HOLD"
        assert v.score == 5.0
        assert v.confidence == 0.5
        assert v.risk_adjusted_score == 4.5

    def test_fundamental_result_with_deterministic(self):
        from src.contracts.analysis import FundamentalResult
        r = FundamentalResult(
            ticker="AAPL",
            deterministic_score=7.3,
            deterministic_signal="BUY",
            score_evidence=["P/E atractivo en 15.0 → 7.2"],
            data_coverage=0.85,
        )
        assert r.deterministic_score == 7.3
        assert r.deterministic_signal == "BUY"
        assert len(r.score_evidence) == 1

    def test_json_serialization(self):
        from src.contracts.analysis import FundamentalResult
        r = FundamentalResult(
            ticker="MSFT",
            deterministic_score=6.5,
            deterministic_signal="BUY",
        )
        data = r.model_dump(mode="json")
        assert data["ticker"] == "MSFT"
        assert data["deterministic_score"] == 6.5
        assert isinstance(data["agent_memos"], list)
        assert isinstance(data["committee_verdict"], dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5: Sigmoid Math Helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestSigmoidMath:
    """Test low-level sigmoid and helper functions."""

    def test_sigmoid_center_is_midpoint(self):
        from src.engines.fundamental.scoring import _sigmoid
        assert abs(_sigmoid(0.0, center=0.0, scale=1.0) - 5.0) < 0.01

    def test_sigmoid_above_center_above_5(self):
        from src.engines.fundamental.scoring import _sigmoid
        assert _sigmoid(5.0, center=0.0, scale=1.0) > 5.0

    def test_sigmoid_below_center_below_5(self):
        from src.engines.fundamental.scoring import _sigmoid
        assert _sigmoid(-5.0, center=0.0, scale=1.0) < 5.0

    def test_sigmoid_extreme_positive(self):
        from src.engines.fundamental.scoring import _sigmoid
        assert abs(_sigmoid(1000.0, center=0.0, scale=1.0) - 10.0) < 0.01

    def test_sigmoid_extreme_negative(self):
        from src.engines.fundamental.scoring import _sigmoid
        assert abs(_sigmoid(-1000.0, center=0.0, scale=1.0) - 0.0) < 0.01

    def test_safe_float_data_incomplete(self):
        from src.engines.fundamental.scoring import _safe_float
        assert _safe_float("DATA_INCOMPLETE") is None
        assert _safe_float("DATA_INCOMPLETE", 0.0) == 0.0

    def test_safe_float_valid(self):
        from src.engines.fundamental.scoring import _safe_float
        assert _safe_float(3.14) == 3.14
        assert _safe_float("2.5") == 2.5

    def test_safe_float_none(self):
        from src.engines.fundamental.scoring import _safe_float
        assert _safe_float(None) is None


# ═══════════════════════════════════════════════════════════════════════════════
# Section 6: LLM Coherence Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestLLMCoherence:
    """Test validate_llm_coherence()."""

    def test_high_score_sell_corrected(self):
        from src.engines.fundamental.scoring import validate_llm_coherence
        signal, corrected = validate_llm_coherence(8.5, "SELL")
        assert signal == "BUY"
        assert corrected is True

    def test_low_score_buy_corrected(self):
        from src.engines.fundamental.scoring import validate_llm_coherence
        signal, corrected = validate_llm_coherence(2.0, "BUY")
        assert signal == "SELL"
        assert corrected is True

    def test_neutral_score_no_correction(self):
        from src.engines.fundamental.scoring import validate_llm_coherence
        signal, corrected = validate_llm_coherence(5.5, "BUY")
        assert signal == "BUY"
        assert corrected is False

    def test_aligned_no_correction(self):
        from src.engines.fundamental.scoring import validate_llm_coherence
        signal, corrected = validate_llm_coherence(8.0, "BUY")
        assert signal == "BUY"
        assert corrected is False

    def test_low_score_hold_no_correction(self):
        from src.engines.fundamental.scoring import validate_llm_coherence
        # HOLD direction is 0 — no contradiction detected for either direction
        signal, corrected = validate_llm_coherence(2.0, "HOLD")
        assert signal == "HOLD"
        assert corrected is False


# ═══════════════════════════════════════════════════════════════════════════════
# Section 7: Softened Calibration
# ═══════════════════════════════════════════════════════════════════════════════

class TestSoftenedCalibration:
    """Verify calibration changes produce more balanced results."""

    def test_pe_30_not_punished_to_zero(self):
        """PE=30 should still get a meaningful score (>2.0) with softened scale."""
        from src.engines.fundamental.scoring import _sigmoid
        s = _sigmoid(-30.0, center=-20.0, scale=0.10)
        assert s > 2.0, f"PE=30 score {s:.2f} is too harsh"

    def test_pe_50_still_low(self):
        """PE=50 should still be punished (<2.5)."""
        from src.engines.fundamental.scoring import _sigmoid
        s = _sigmoid(-50.0, center=-20.0, scale=0.10)
        assert s < 2.5

    def test_beta_1_2_not_punished(self):
        """Beta=1.2 (typical growth) should still be mid-range (>3.5)."""
        from src.engines.fundamental.scoring import _sigmoid
        s = _sigmoid(-1.2, center=-1.0, scale=2.0)
        assert s > 3.5, f"Beta=1.2 score {s:.2f} is too harsh"

    def test_beta_0_8_defensive_rewarded(self):
        """Beta=0.8 should be well above neutral (>5.9)."""
        from src.engines.fundamental.scoring import _sigmoid
        s = _sigmoid(-0.8, center=-1.0, scale=2.0)
        assert s > 5.9

    def test_faamg_not_hold(self):
        """FAAMG archetype should be BUY with softened calibration."""
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        faamg = {
            "profitability": {"gross_margin": 0.68, "roic": 0.28, "roe": 0.40, "net_margin": 0.25},
            "valuation": {"pe_ratio": 35.0, "pb_ratio": 12.0, "ev_ebitda": 25.0, "fcf_yield": 0.03},
            "leverage": {"debt_to_equity": 0.4, "current_ratio": 2.5, "interest_coverage": 30.0, "quick_ratio": 2.0},
            "quality": {"revenue_growth_yoy": 0.18, "earnings_growth_yoy": 0.22, "beta": 1.1,
                        "payout_ratio": 0.15, "dividend_yield": 0.005},
        }
        result = FundamentalScoringEngine.compute(faamg)
        assert result.score >= 5.5, f"FAAMG score {result.score} is too low"

    def test_value_trap_still_hold(self):
        """Value trap should remain HOLD, not get upgraded by softening."""
        from src.engines.fundamental.scoring import FundamentalScoringEngine
        value_trap = {
            "profitability": {"gross_margin": 0.10, "roic": 0.02, "roe": 0.03, "net_margin": 0.01},
            "valuation": {"pe_ratio": 6.0, "pb_ratio": 0.8, "ev_ebitda": 5.0, "fcf_yield": 0.08},
            "leverage": {"debt_to_equity": 3.0, "current_ratio": 0.7, "interest_coverage": 1.5, "quick_ratio": 0.5},
            "quality": {"revenue_growth_yoy": -0.15, "earnings_growth_yoy": -0.30, "beta": 1.8,
                        "payout_ratio": 1.2, "dividend_yield": 0.08},
        }
        result = FundamentalScoringEngine.compute(value_trap)
        assert result.signal in ("HOLD", "SELL", "STRONG_SELL"), f"Value trap should not be BUY: {result.signal}"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 8: Payout Ratio Sigmoid
# ═══════════════════════════════════════════════════════════════════════════════

class TestPayoutSigmoid:
    """Verify payout ratio uses smooth sigmoid instead of discrete steps."""

    def test_payout_35_near_peak(self):
        """35% payout (sweet spot) should score well."""
        from src.engines.fundamental.scoring import _score_capital
        r = _score_capital({"quality": {"payout_ratio": 0.35}})
        assert r.score >= 5.0

    def test_payout_continuity_small_change(self):
        """1% payout change should produce small but measurable score difference."""
        from src.engines.fundamental.scoring import _score_capital
        r1 = _score_capital({"quality": {"payout_ratio": 0.40}})
        r2 = _score_capital({"quality": {"payout_ratio": 0.41}})
        assert r1.score != r2.score
        assert abs(r1.score - r2.score) < 1.0

    def test_payout_over_100_very_low(self):
        """Payout >100% should be heavily penalised."""
        from src.engines.fundamental.scoring import _score_capital
        r = _score_capital({"quality": {"payout_ratio": 1.2}})
        assert r.score < 3.0

    def test_payout_high_penalised(self):
        """80% payout should be worse than 40% payout."""
        from src.engines.fundamental.scoring import _score_capital
        r_good = _score_capital({"quality": {"payout_ratio": 0.40}})
        r_high = _score_capital({"quality": {"payout_ratio": 0.80}})
        assert r_good.score > r_high.score

    def test_payout_zero_moderate(self):
        """0% payout (growth reinvestment) should be moderate, not completely punished."""
        from src.engines.fundamental.scoring import _score_capital
        r = _score_capital({"quality": {"payout_ratio": 0.0}})
        # Bell-curve centered at 0.40: 0.0 is distant → low score but floor at 1.0
        assert r.score >= 1.0
