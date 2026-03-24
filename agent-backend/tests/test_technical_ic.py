"""
tests/test_technical_ic.py
──────────────────────────────────────────────────────────────────────────────
Test suite for the Technical IC "War Room" module.

Tests:
  - Model validation (all Pydantic schemas)
  - Conflict identification (disagreement algorithm)
  - Regime-weighted conviction voting
  - Engine anchoring guardrail
  - Head Technician synthesis (deterministic paths)
  - Full debate orchestration (mocked LLM)
"""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock

# ─── Models ──────────────────────────────────────────────────────────────────

from src.engines.technical.war_room.models import (
    TacticalMember,
    TacticalAssessment,
    TacticalConflict,
    TimeframeAssessment,
    TacticalVote,
    TechnicalICTranscript,
    TechnicalICVerdict,
    ActionPlan,
)


class TestModels:
    """Validate all Pydantic schemas."""

    def test_tactical_member(self):
        m = TacticalMember(
            name="Test Agent", role="Tester", domain="trend",
            framework="Test Framework", bias_description="Test bias",
        )
        assert m.name == "Test Agent"
        assert m.domain == "trend"

    def test_tactical_assessment(self):
        a = TacticalAssessment(
            agent="Test Agent", domain="trend", signal="BULLISH",
            conviction=0.85, thesis="Test thesis",
            supporting_data=["data1", "data2"],
        )
        assert a.signal == "BULLISH"
        assert a.conviction == 0.85
        assert len(a.supporting_data) == 2

    def test_tactical_assessment_conviction_bounds(self):
        """Conviction must be 0.0–1.0."""
        with pytest.raises(Exception):
            TacticalAssessment(
                agent="X", domain="trend", signal="BULLISH", conviction=1.5,
                thesis="Test",
            )

    def test_tactical_conflict(self):
        c = TacticalConflict(
            challenger="A", target="B", disagreement="Disagree on RSI",
            severity="HIGH",
        )
        assert c.severity == "HIGH"

    def test_timeframe_assessment(self):
        tf = TimeframeAssessment(
            agent="Test", timeframe_alignment="ALIGNED",
            dominant_timeframe="1D",
            timeframe_readings={"1D": "BULLISH", "1W": "BULLISH"},
        )
        assert tf.timeframe_alignment == "ALIGNED"

    def test_tactical_vote(self):
        v = TacticalVote(
            agent="Test", signal="BEARISH", conviction=0.6,
            conviction_drift=-0.1, regime_weight=1.3, dissents=True,
        )
        assert v.dissents is True
        assert v.regime_weight == 1.3

    def test_action_plan(self):
        ap = ActionPlan(
            entry_zone="$175–$177",
            stop_loss="$172.80",
            take_profit_1="$185",
            risk_reward="1:2.4",
        )
        assert "$175" in ap.entry_zone

    def test_technical_ic_verdict(self):
        v = TechnicalICVerdict(
            signal="BUY", confidence=0.78,
            consensus_strength="strong_majority",
            narrative="Test narrative",
            vote_breakdown={"BULLISH": 4, "NEUTRAL": 1, "BEARISH": 1},
        )
        assert v.signal == "BUY"
        assert v.vote_breakdown["BULLISH"] == 4

    def test_transcript(self):
        t = TechnicalICTranscript(
            ticker="AAPL",
            members=[TacticalMember(
                name="T", role="R", domain="trend",
                framework="F", bias_description="B",
            )],
        )
        assert t.ticker == "AAPL"
        assert len(t.members) == 1
        assert t.round_1_assessments == []

    def test_full_model_dump(self):
        """Ensure all models serialize to JSON cleanly."""
        t = TechnicalICTranscript(
            ticker="NVDA",
            round_1_assessments=[
                TacticalAssessment(
                    agent="T", domain="trend", signal="BULLISH",
                    conviction=0.7, thesis="Test",
                ),
            ],
            round_4_votes=[
                TacticalVote(agent="T", signal="BULLISH", conviction=0.7),
            ],
            verdict=TechnicalICVerdict(
                signal="BUY", confidence=0.7,
                consensus_strength="majority",
            ),
        )
        data = t.model_dump(mode="json")
        assert data["ticker"] == "NVDA"
        assert json.dumps(data)  # must be JSON-serializable


# ─── Conflict Identification ─────────────────────────────────────────────────

from src.engines.technical.war_room.debate import _disagreement, _assign_conflicts


class TestConflictIdentification:
    """Test the disagreement scoring and conflict assignment."""

    def test_max_disagreement(self):
        """BULLISH vs BEARISH with high conviction = max disagreement."""
        a = TacticalAssessment(
            agent="A", domain="trend", signal="BULLISH", conviction=0.9, thesis="T",
        )
        b = TacticalAssessment(
            agent="B", domain="momentum", signal="BEARISH", conviction=0.9, thesis="T",
        )
        score = _disagreement(a, b)
        assert score > 1.5  # signal distance 2 + conviction boost

    def test_no_disagreement_same_signal(self):
        """Same signal and conviction = minimal disagreement."""
        a = TacticalAssessment(
            agent="A", domain="trend", signal="BULLISH", conviction=0.5, thesis="T",
        )
        b = TacticalAssessment(
            agent="B", domain="momentum", signal="BULLISH", conviction=0.5, thesis="T",
        )
        score = _disagreement(a, b)
        assert score < 1.0

    def test_assign_conflicts_routes_to_max_opponent(self):
        """Each agent should challenge their maximum opponent."""
        assessments = [
            TacticalAssessment(agent="Bull1", domain="trend", signal="BULLISH", conviction=0.9, thesis="T"),
            TacticalAssessment(agent="Bear1", domain="momentum", signal="BEARISH", conviction=0.9, thesis="T"),
            TacticalAssessment(agent="Neutral1", domain="volatility", signal="NEUTRAL", conviction=0.5, thesis="T"),
        ]
        assignments = _assign_conflicts(assessments)
        assert assignments["Bull1"] == "Bear1"
        assert assignments["Bear1"] == "Bull1"


# ─── Engine Anchoring Guardrail ──────────────────────────────────────────────

from src.engines.technical.war_room.head_technician import _validate_direction


class TestGuardrail:
    """Test the engine anchoring guardrail."""

    def test_bullish_ic_bearish_engine_forces_alignment(self):
        """IC says BUY but engine says SELL → force to SELL."""
        result = _validate_direction("BUY", "SELL")
        assert result == "SELL"

    def test_bearish_ic_bullish_engine_forces_alignment(self):
        """IC says SELL but engine says BUY → force to BUY."""
        result = _validate_direction("STRONG_SELL", "BUY")
        assert result == "BUY"

    def test_same_direction_passes_through(self):
        """IC and engine both bullish → IC signal passes through."""
        result = _validate_direction("STRONG_BUY", "BUY")
        assert result == "STRONG_BUY"

    def test_neutral_ic_with_bullish_engine_passes(self):
        """IC says NEUTRAL, engine says BUY → NEUTRAL passes (not contradiction)."""
        result = _validate_direction("NEUTRAL", "BUY")
        assert result == "NEUTRAL"

    def test_neutral_engine_allows_any_ic(self):
        """Engine NEUTRAL allows IC to say anything."""
        assert _validate_direction("BUY", "NEUTRAL") == "BUY"
        assert _validate_direction("SELL", "NEUTRAL") == "SELL"
        assert _validate_direction("NEUTRAL", "NEUTRAL") == "NEUTRAL"


# ─── Conviction Voting ──────────────────────────────────────────────────────

from src.engines.technical.war_room.debate import TechnicalWarRoom, REGIME_AGENT_WEIGHTS
from src.engines.technical.war_room.agents import WAR_ROOM_MEMBERS


class TestConvictionVoting:
    """Test regime-weighted conviction voting (Round 4)."""

    def test_vote_count_matches_members(self):
        """Each member produces exactly one vote."""
        assessments = [
            TacticalAssessment(
                agent=m.name, domain=m.domain, signal="BULLISH",
                conviction=0.7, thesis="Test",
            )
            for m in WAR_ROOM_MEMBERS
        ]
        timeframes = [
            TimeframeAssessment(
                agent=m.name, timeframe_alignment="ALIGNED",
                dominant_timeframe="1D", conviction_adjustment=0.0,
            )
            for m in WAR_ROOM_MEMBERS
        ]
        debate = TechnicalWarRoom()
        votes = debate._round_conviction(assessments, timeframes, "TRENDING")
        assert len(votes) == len(WAR_ROOM_MEMBERS)

    def test_regime_weights_applied(self):
        """In TRENDING regime, Trend Strategist gets higher weight."""
        assessments = [
            TacticalAssessment(
                agent=m.name, domain=m.domain, signal="BULLISH",
                conviction=0.7, thesis="Test",
            )
            for m in WAR_ROOM_MEMBERS
        ]
        timeframes = [
            TimeframeAssessment(
                agent=m.name, timeframe_alignment="ALIGNED",
                dominant_timeframe="1D", conviction_adjustment=0.0,
            )
            for m in WAR_ROOM_MEMBERS
        ]
        debate = TechnicalWarRoom()
        votes = debate._round_conviction(assessments, timeframes, "TRENDING")
        trend_vote = next(v for v in votes if v.agent == "Trend Strategist")
        struct_vote = next(v for v in votes if v.agent == "Structure Analyst")
        assert trend_vote.regime_weight > struct_vote.regime_weight

    def test_low_conviction_shifts_to_neutral(self):
        """If conviction drops below 0.3, signal shifts to NEUTRAL."""
        assessments = [
            TacticalAssessment(
                agent=WAR_ROOM_MEMBERS[0].name,
                domain=WAR_ROOM_MEMBERS[0].domain,
                signal="BULLISH", conviction=0.4, thesis="Test",
            ),
        ]
        # Large negative adjustment drops conviction below 0.3
        timeframes = [
            TimeframeAssessment(
                agent=WAR_ROOM_MEMBERS[0].name,
                timeframe_alignment="DIVERGENT",
                dominant_timeframe="1D",
                conviction_adjustment=-0.2,
            ),
        ]
        debate = TechnicalWarRoom(members=[WAR_ROOM_MEMBERS[0]])
        votes = debate._round_conviction(assessments, timeframes, "TRANSITIONING")
        assert votes[0].signal == "NEUTRAL"
        assert votes[0].conviction < 0.3

    def test_dissent_detection(self):
        """Agent opposing majority is flagged as dissenting."""
        members = WAR_ROOM_MEMBERS[:3]
        assessments = [
            TacticalAssessment(agent=members[0].name, domain=members[0].domain, signal="BULLISH", conviction=0.8, thesis="T"),
            TacticalAssessment(agent=members[1].name, domain=members[1].domain, signal="BULLISH", conviction=0.8, thesis="T"),
            TacticalAssessment(agent=members[2].name, domain=members[2].domain, signal="BEARISH", conviction=0.8, thesis="T"),
        ]
        timeframes = [
            TimeframeAssessment(agent=m.name, timeframe_alignment="ALIGNED", dominant_timeframe="1D")
            for m in members
        ]
        debate = TechnicalWarRoom(members=members)
        votes = debate._round_conviction(assessments, timeframes, "TRANSITIONING")
        bearish_vote = next(v for v in votes if v.agent == members[2].name)
        assert bearish_vote.dissents is True


# ─── Head Technician Synthesis ───────────────────────────────────────────────

from src.engines.technical.war_room.head_technician import HeadTechnicianSynthesizer


class TestHeadTechnician:
    """Test deterministic paths of the Head Technician synthesis."""

    def test_empty_votes_fallback(self):
        """No votes → returns engine signal with contested consensus."""
        transcript = TechnicalICTranscript(ticker="TEST")
        verdict = HeadTechnicianSynthesizer.synthesize(
            "TEST", transcript, engine_signal="BUY", engine_score=7.0,
        )
        assert verdict.signal == "BUY"
        assert verdict.consensus_strength == "contested"

    @patch("src.engines.technical.war_room.head_technician._invoke_llm_for_synthesis")
    def test_unanimous_bullish(self, mock_llm):
        """All agents BULLISH → unanimous consensus."""
        mock_llm.return_value = {
            "narrative": "All analysts agree on bullish thesis.",
            "action_plan": {
                "entry_zone": "$175–$177",
                "stop_loss": "$172",
            },
            "key_levels": "R: $185, S: $172",
            "timing": "Enter on pullback",
            "risk_factors": ["Overbought RSI"],
        }
        transcript = TechnicalICTranscript(
            ticker="TEST",
            round_4_votes=[
                TacticalVote(agent=f"Agent{i}", signal="BULLISH", conviction=0.8, regime_weight=1.0)
                for i in range(6)
            ],
        )
        verdict = HeadTechnicianSynthesizer.synthesize(
            "TEST", transcript, engine_signal="BUY", engine_score=7.0,
        )
        assert verdict.consensus_strength == "unanimous"
        assert verdict.vote_breakdown["BULLISH"] == 6
        assert "BUY" in verdict.signal or "STRONG_BUY" in verdict.signal

    @patch("src.engines.technical.war_room.head_technician._invoke_llm_for_synthesis")
    def test_guardrail_overrides_contradiction(self, mock_llm):
        """IC BEARISH but engine BULLISH → guardrail forces alignment."""
        mock_llm.return_value = {"narrative": "Test", "risk_factors": []}
        transcript = TechnicalICTranscript(
            ticker="TEST",
            round_4_votes=[
                TacticalVote(agent=f"Agent{i}", signal="BEARISH", conviction=0.9, regime_weight=1.0)
                for i in range(6)
            ],
        )
        verdict = HeadTechnicianSynthesizer.synthesize(
            "TEST", transcript, engine_signal="BUY", engine_score=7.0,
        )
        # Guardrail should force the signal to match engine direction
        assert verdict.signal == "BUY"


# ─── Full Debate Orchestration ───────────────────────────────────────────────

class TestDebateOrchestration:
    """Test full debate flow with mocked LLM calls."""

    @patch("src.observability.traced_llm_call")
    def test_full_debate_produces_transcript(self, mock_llm):
        """Full 5-round debate produces a complete transcript."""
        # Mock LLM to return valid JSON for each agent call
        mock_llm.return_value = json.dumps({
            "signal": "BULLISH",
            "conviction": 0.75,
            "thesis": "Test thesis with RSI at 55 and SMA50 above SMA200.",
            "supporting_data": ["RSI: 55", "SMA50 > SMA200"],
            "theoretical_framework": "Dow Theory confirms uptrend.",
            "cross_module_note": "Volume confirms the move.",
            "disagreement": "Target's bearish reading ignores the trend.",
            "challenger_evidence": ["SMA50 above SMA200"],
            "theoretical_basis": "Dow Theory",
            "severity": "MEDIUM",
            "timeframe_alignment": "ALIGNED",
            "dominant_timeframe": "1D",
            "timeframe_readings": {"1D": "BULLISH", "1W": "BULLISH"},
            "conviction_adjustment": 0.05,
            "defense": "Trend confirmed across timeframes.",
            "narrative": "Unanimous bullish consensus.",
            "action_plan": {"entry_zone": "$175", "stop_loss": "$170"},
            "key_levels": "S: $170, R: $185",
            "timing": "Enter now",
            "risk_factors": ["RSI approaching overbought"],
        })

        engine_data = {
            "module_scores": [
                {"name": "trend", "score": 7.0, "signal": "BULLISH", "evidence": ["SMA50 > SMA200"], "details": {}},
                {"name": "momentum", "score": 6.0, "signal": "BULLISH", "evidence": ["RSI: 55"], "details": {}},
                {"name": "volatility", "score": 5.5, "signal": "NORMAL", "evidence": ["ATR: 1.8%"], "details": {}},
                {"name": "volume", "score": 6.5, "signal": "NORMAL", "evidence": ["Vol: 1.2x avg"], "details": {}},
                {"name": "structure", "score": 6.0, "signal": "BULLISH", "evidence": ["HH/HL"], "details": {}},
                {"name": "mtf", "score": 6.5, "signal": "BUY", "evidence": ["MTF aligned"], "details": {}},
            ],
            "engine_signal": "BUY",
            "engine_score": 6.5,
            "regime": {"trend_regime": "TRENDING", "adx": 30.0},
            "asset_context": {"optimal_atr_pct": 1.8, "avg_daily_range_pct": 2.0, "bb_width_median": 4.0},
            "sector_relative": {"status": "OUTPERFORMING", "relative_strength": 0.3},
            "mtf_data": {"1D": {"signal": "BUY", "score": 7.0}},
        }

        debate = TechnicalWarRoom()
        transcript = asyncio.run(debate.run_full("TEST", engine_data))

        assert transcript.ticker == "TEST"
        assert len(transcript.round_1_assessments) == 6
        assert len(transcript.round_2_conflicts) >= 1
        assert len(transcript.round_3_timeframes) >= 1
        assert len(transcript.round_4_votes) == 6
        assert transcript.verdict is not None
        assert transcript.verdict.signal in ("STRONG_BUY", "BUY", "NEUTRAL")

    @patch("src.observability.traced_llm_call")
    def test_stream_yields_correct_events(self, mock_llm):
        """SSE stream emits events in correct order."""
        mock_llm.return_value = json.dumps({
            "signal": "NEUTRAL",
            "conviction": 0.5,
            "thesis": "Neutral reading.",
            "supporting_data": [],
            "theoretical_framework": "Test",
            "cross_module_note": "",
            "disagreement": "Minor disagreement.",
            "challenger_evidence": [],
            "theoretical_basis": "Test",
            "severity": "LOW",
            "timeframe_alignment": "PARTIAL",
            "dominant_timeframe": "1D",
            "timeframe_readings": {},
            "conviction_adjustment": 0.0,
            "defense": "Maintained.",
            "narrative": "Neutral consensus.",
            "action_plan": {},
            "key_levels": "",
            "timing": "",
            "risk_factors": [],
        })

        engine_data = {
            "module_scores": [
                {"name": d, "score": 5.0, "signal": "NEUTRAL", "evidence": [], "details": {}}
                for d in ["trend", "momentum", "volatility", "volume", "structure", "mtf"]
            ],
            "engine_signal": "NEUTRAL",
            "engine_score": 5.0,
            "regime": {"trend_regime": "TRANSITIONING"},
            "asset_context": {},
            "sector_relative": {},
            "mtf_data": None,
        }

        debate = TechnicalWarRoom()

        async def _collect():
            events = []
            async for ev in debate.run_stream("TEST", engine_data):
                events.append(ev["event"])
            return events

        event_names = asyncio.run(_collect())

        # Verify order
        assert event_names[0] == "tic_members"
        assert "tic_round_assess" in event_names
        assert "tic_round_conflict" in event_names
        assert "tic_round_timeframe" in event_names
        assert "tic_round_vote" in event_names
        assert "tic_verdict" in event_names
        assert event_names[-1] == "tic_done"


# ─── Agent Roster ────────────────────────────────────────────────────────────

class TestAgentRoster:
    """Validate the 6 War Room agent definitions."""

    def test_six_agents_defined(self):
        assert len(WAR_ROOM_MEMBERS) == 6

    def test_all_domains_covered(self):
        domains = {m.domain for m in WAR_ROOM_MEMBERS}
        assert domains == {"trend", "momentum", "volatility", "volume", "structure", "mtf"}

    def test_all_agents_have_framework(self):
        for m in WAR_ROOM_MEMBERS:
            assert len(m.framework) > 10, f"{m.name} missing framework"

    def test_regime_weights_cover_all_agents(self):
        for regime, weights in REGIME_AGENT_WEIGHTS.items():
            for m in WAR_ROOM_MEMBERS:
                assert m.name in weights, f"{m.name} missing from {regime} weights"
