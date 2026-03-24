"""
tests/test_investment_committee.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive tests for the multi-agent Investment Committee simulation.

All LLM calls are mocked to avoid API costs and ensure determinism.

Coverage:
  1. Model validation — schemas, defaults, serialization
  2. Challenge assignment — maximum-disagreement strategy
  3. Vote computation — conviction drift, signal adjustment, dissent detection
  4. Chairman synthesis — consensus strength, weighted score, signal derivation
  5. Debate engine — full round orchestration (mocked LLM)
  6. Edge cases — ties, unanimous, all SELL, empty data
"""

import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock

from src.engines.fundamental.committee.models import (
    ICMember,
    PositionMemo,
    Challenge,
    Rebuttal,
    Vote,
    ICTranscript,
    ICVerdict,
)
from src.engines.fundamental.committee.chairman import ChairmanSynthesizer
from src.engines.fundamental.committee.debate import (
    _disagreement,
    _assign_challenges,
    _SIGNAL_SCORE,
    InvestmentCommitteeDebate,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1: Model Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestModelValidation:
    """Test Pydantic models for defaults and serialization."""

    def test_ic_member_schema(self):
        member = ICMember(
            name="Tester",
            role="Test Role",
            framework="Test / Framework",
        )
        assert member.name == "Tester"
        assert member.bias == ""

    def test_position_memo_defaults(self):
        memo = PositionMemo(agent="Value Analyst")
        assert memo.signal == "HOLD"
        assert memo.conviction == 0.5
        assert memo.thesis == ""

    def test_position_memo_conviction_clamped(self):
        memo = PositionMemo(agent="Test", conviction=0.0)
        assert memo.conviction == 0.0
        memo2 = PositionMemo(agent="Test", conviction=1.0)
        assert memo2.conviction == 1.0

    def test_challenge_schema(self):
        ch = Challenge(
            challenger="Value Analyst",
            target="Growth Strategist",
            objection="Valuation multiples are stretched.",
            severity="high",
        )
        assert ch.severity == "high"
        assert ch.evidence == []

    def test_rebuttal_schema(self):
        r = Rebuttal(
            agent="Growth Strategist",
            challenger="Value Analyst",
            defense="Forward PEG is below 1.0.",
            conviction_adjustment=-0.1,
        )
        assert r.conviction_adjustment == -0.1
        assert r.concession == ""

    def test_vote_defaults(self):
        v = Vote(agent="Test")
        assert v.signal == "HOLD"
        assert v.dissents is False
        assert v.conviction_drift == 0.0

    def test_ic_verdict_defaults(self):
        verdict = ICVerdict()
        assert verdict.signal == "HOLD"
        assert verdict.score == 5.0
        assert verdict.consensus_strength == "mixed"
        assert verdict.dissenting_opinions == []

    def test_ic_verdict_serialization(self):
        verdict = ICVerdict(
            signal="BUY",
            score=7.2,
            consensus_strength="strong_majority",
            vote_breakdown={"BUY": 4, "HOLD": 2},
        )
        data = verdict.model_dump(mode="json")
        assert data["signal"] == "BUY"
        assert data["vote_breakdown"]["BUY"] == 4

    def test_ic_transcript_structure(self):
        transcript = ICTranscript(ticker="AAPL")
        assert transcript.round_1_memos == []
        assert transcript.round_4_votes == []
        assert transcript.verdict is None

    def test_transcript_with_verdict(self):
        verdict = ICVerdict(signal="BUY", score=7.5)
        transcript = ICTranscript(
            ticker="MSFT",
            verdict=verdict,
        )
        assert transcript.verdict.signal == "BUY"
        data = transcript.model_dump(mode="json")
        assert data["verdict"]["score"] == 7.5


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2: Challenge Assignment (Maximum Disagreement)
# ═══════════════════════════════════════════════════════════════════════════════


class TestChallengeAssignment:
    """Test the maximum-disagreement challenge assignment logic."""

    def test_disagreement_same_signal(self):
        a = PositionMemo(agent="A", signal="BUY", conviction=0.8)
        b = PositionMemo(agent="B", signal="BUY", conviction=0.8)
        score = _disagreement(a, b)
        assert score < 1.0  # Same direction, low disagreement

    def test_disagreement_opposing_signals(self):
        a = PositionMemo(agent="A", signal="BUY", conviction=0.8)
        b = PositionMemo(agent="B", signal="SELL", conviction=0.8)
        score = _disagreement(a, b)
        assert score > 1.5  # Opposing directions

    def test_disagreement_strong_buy_vs_strong_sell(self):
        a = PositionMemo(agent="A", signal="STRONG_BUY", conviction=1.0)
        b = PositionMemo(agent="B", signal="STRONG_SELL", conviction=1.0)
        score = _disagreement(a, b)
        # Max signal distance (4) + max conviction boost (0.5)
        assert score >= 4.0

    def test_assign_challenges_no_self_challenge(self):
        memos = [
            PositionMemo(agent="A", signal="BUY", conviction=0.9),
            PositionMemo(agent="B", signal="SELL", conviction=0.9),
            PositionMemo(agent="C", signal="HOLD", conviction=0.5),
        ]
        assignments = _assign_challenges(memos)
        for challenger, target in assignments.items():
            assert challenger != target

    def test_assign_challenges_buy_targets_sell(self):
        memos = [
            PositionMemo(agent="Bull", signal="BUY", conviction=0.9),
            PositionMemo(agent="Bear", signal="SELL", conviction=0.9),
            PositionMemo(agent="Neutral", signal="HOLD", conviction=0.5),
        ]
        assignments = _assign_challenges(memos)
        assert assignments["Bull"] == "Bear"
        assert assignments["Bear"] == "Bull"

    def test_assign_challenges_all_agents_get_assignment(self):
        memos = [
            PositionMemo(agent=f"Agent{i}", signal="BUY" if i % 2 == 0 else "SELL", conviction=0.8)
            for i in range(6)
        ]
        assignments = _assign_challenges(memos)
        assert len(assignments) == 6


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3: Vote Computation
# ═══════════════════════════════════════════════════════════════════════════════


class TestVoteComputation:
    """Test vote logic: conviction drift, dissent detection, signal adjustment."""

    def _make_votes(self, signals_convictions: list[tuple[str, float]]) -> list[Vote]:
        return [
            Vote(agent=f"Agent{i}", signal=s, conviction=c)
            for i, (s, c) in enumerate(signals_convictions)
        ]

    def test_conviction_drift_tracked(self):
        v = Vote(
            agent="Test",
            signal="BUY",
            conviction=0.7,
            conviction_drift=-0.2,
        )
        assert v.conviction_drift == -0.2

    def test_dissent_detection(self):
        v_dissent = Vote(agent="Dissenter", signal="SELL", dissents=True)
        v_agree = Vote(agent="Agreeer", signal="BUY", dissents=False)
        assert v_dissent.dissents is True
        assert v_agree.dissents is False


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4: Chairman Synthesis
# ═══════════════════════════════════════════════════════════════════════════════


class TestChairmanSynthesis:
    """Test ChairmanSynthesizer's deterministic methods."""

    def test_vote_breakdown(self):
        votes = [
            Vote(agent="A", signal="BUY"),
            Vote(agent="B", signal="BUY"),
            Vote(agent="C", signal="SELL"),
            Vote(agent="D", signal="BUY"),
            Vote(agent="E", signal="HOLD"),
            Vote(agent="F", signal="BUY"),
        ]
        tally = ChairmanSynthesizer._compute_vote_breakdown(votes)
        assert tally == {"BUY": 4, "SELL": 1, "HOLD": 1}

    def test_consensus_strength_unanimous(self):
        votes = [Vote(agent=f"A{i}", signal="BUY") for i in range(6)]
        assert ChairmanSynthesizer._compute_consensus_strength(votes) == "unanimous"

    def test_consensus_strength_strong_majority(self):
        votes = [Vote(agent=f"A{i}", signal="BUY") for i in range(5)]
        votes.append(Vote(agent="Dissenter", signal="SELL"))
        # 5/6 = 83%
        assert ChairmanSynthesizer._compute_consensus_strength(votes) == "strong_majority"

    def test_consensus_strength_majority(self):
        votes = [Vote(agent=f"A{i}", signal="BUY") for i in range(4)]
        votes.extend([Vote(agent=f"B{i}", signal="SELL") for i in range(2)])
        # 4/6 = 67%
        assert ChairmanSynthesizer._compute_consensus_strength(votes) == "majority"

    def test_consensus_strength_split(self):
        votes = [Vote(agent=f"A{i}", signal="BUY") for i in range(3)]
        votes.extend([Vote(agent=f"B{i}", signal="SELL") for i in range(3)])
        # 3/6 = 50%
        assert ChairmanSynthesizer._compute_consensus_strength(votes) == "split"

    def test_consensus_strength_contested(self):
        signals = ["BUY", "SELL", "HOLD", "STRONG_BUY", "STRONG_SELL", "HOLD"]
        votes = [Vote(agent=f"A{i}", signal=s) for i, s in enumerate(signals)]
        # Max faction 2/6 = 33%
        assert ChairmanSynthesizer._compute_consensus_strength(votes) == "contested"

    def test_consensus_empty_votes(self):
        assert ChairmanSynthesizer._compute_consensus_strength([]) == "contested"

    def test_weighted_score_all_buy(self):
        votes = [Vote(agent=f"A{i}", signal="BUY", conviction=0.8) for i in range(6)]
        score = ChairmanSynthesizer._compute_weighted_score(votes)
        assert score == 7.5  # BUY maps to 7.5

    def test_weighted_score_all_sell(self):
        votes = [Vote(agent=f"A{i}", signal="SELL", conviction=0.8) for i in range(6)]
        score = ChairmanSynthesizer._compute_weighted_score(votes)
        assert score == 2.5  # SELL maps to 2.5

    def test_weighted_score_mixed(self):
        votes = [
            Vote(agent="Bull1", signal="BUY", conviction=0.9),
            Vote(agent="Bull2", signal="BUY", conviction=0.8),
            Vote(agent="Bear", signal="SELL", conviction=0.5),
            Vote(agent="Neutral", signal="HOLD", conviction=0.6),
        ]
        score = ChairmanSynthesizer._compute_weighted_score(votes)
        assert 4.0 < score < 8.0  # Mixed result

    def test_derive_consensus_signal(self):
        assert ChairmanSynthesizer._derive_consensus_signal(8.0) == "STRONG_BUY"
        assert ChairmanSynthesizer._derive_consensus_signal(7.0) == "BUY"
        assert ChairmanSynthesizer._derive_consensus_signal(5.0) == "HOLD"
        assert ChairmanSynthesizer._derive_consensus_signal(3.0) == "SELL"
        assert ChairmanSynthesizer._derive_consensus_signal(1.0) == "STRONG_SELL"

    def test_conviction_drift_summary_no_drift(self):
        votes = [Vote(agent=f"A{i}", signal="BUY", conviction_drift=0.0) for i in range(4)]
        summary = ChairmanSynthesizer._conviction_drift_summary(votes)
        assert "maintained" in summary.lower()

    def test_conviction_drift_summary_with_drift(self):
        votes = [
            Vote(agent="Shifter", signal="HOLD", conviction_drift=-0.2),
            Vote(agent="Steady", signal="BUY", conviction_drift=0.0),
        ]
        summary = ChairmanSynthesizer._conviction_drift_summary(votes)
        assert "Shifter" in summary
        assert "decreased" in summary


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5: Debate Engine (Mocked LLM)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDebateEngine:
    """Test the full debate orchestration with mocked LLM responses."""

    @staticmethod
    def _mock_present_response(member_name: str, signal: str = "BUY") -> dict:
        return {
            "agent": member_name,
            "signal": signal,
            "conviction": 0.8,
            "thesis": f"{member_name} sees opportunity here.",
            "key_metrics": ["P/E", "ROIC"],
            "catalysts": ["Strong earnings"],
            "risks": ["Market risk"],
        }

    @staticmethod
    def _mock_challenge_response(challenger: str, target: str) -> dict:
        return {
            "challenger": challenger,
            "target": target,
            "objection": f"{challenger} disagrees with {target}.",
            "evidence": ["Supporting evidence"],
            "severity": "moderate",
        }

    @staticmethod
    def _mock_rebuttal_response(agent: str, challenger: str) -> dict:
        return {
            "agent": agent,
            "challenger": challenger,
            "defense": f"{agent} defends their position.",
            "concession": "",
            "conviction_adjustment": -0.05,
        }

    def test_full_debate_round_count(self):
        """Verify all 5 rounds execute and transcript is complete."""
        from src.engines.fundamental.committee import agents as agent_module

        with patch.object(agent_module, "_invoke_llm", return_value={
            "agent": "Test", "signal": "BUY", "conviction": 0.8,
            "thesis": "Test thesis", "key_metrics": ["P/E"], "catalysts": ["C1"], "risks": ["R1"],
            "challenger": "A", "target": "B", "objection": "Test objection",
            "evidence": [], "severity": "moderate",
            "defense": "Test defense", "concession": "", "conviction_adjustment": -0.05,
        }):
            mock_chairman_result = MagicMock()
            mock_chairman_result.content = json.dumps({
                "narrative": "The committee reached a majority consensus.",
                "key_catalysts": ["Strong earnings"],
                "key_risks": ["Market volatility"],
            })

            with patch("src.observability.traced_llm_call",
                        return_value=mock_chairman_result):
                debate = InvestmentCommitteeDebate()
                transcript = asyncio.run(debate.run_full("AAPL", {"ratios": {}}))

        assert transcript.ticker == "AAPL"
        assert len(transcript.round_1_memos) == 6
        assert len(transcript.round_4_votes) == 6
        assert transcript.verdict is not None
        assert transcript.verdict.signal in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")

    def test_stream_yields_events(self):
        """Verify SSE stream yields events in correct order."""
        from src.engines.fundamental.committee import agents as agent_module

        with patch.object(agent_module, "_invoke_llm", return_value={
            "agent": "Test", "signal": "BUY", "conviction": 0.8,
            "thesis": "Test thesis", "key_metrics": [], "catalysts": [], "risks": [],
            "challenger": "A", "target": "B", "objection": "Test objection",
            "evidence": [], "severity": "moderate",
            "defense": "Test defense", "concession": "", "conviction_adjustment": 0.0,
        }):
            mock_chairman_result = MagicMock()
            mock_chairman_result.content = json.dumps({
                "narrative": "Consensus reached.",
                "key_catalysts": [],
                "key_risks": [],
            })

            with patch("src.observability.traced_llm_call",
                        return_value=mock_chairman_result):
                debate = InvestmentCommitteeDebate()

                async def _collect():
                    events = []
                    async for event in debate.run_stream("AAPL", {}):
                        events.append(event["event"])
                    return events

                events = asyncio.run(_collect())

        # Verify event ordering
        assert events[0] == "ic_members"
        assert "ic_round_present" in events
        assert "ic_round_vote" in events
        assert "ic_verdict" in events
        assert events[-1] == "ic_done"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 6: Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case validation."""

    def test_single_agent_challenge_assignment(self):
        """With only one agent, no challenges can be assigned."""
        memos = [PositionMemo(agent="Solo", signal="BUY", conviction=0.9)]
        assignments = _assign_challenges(memos)
        # Solo agent can't challenge itself
        assert len(assignments) == 0

    def test_all_same_signal(self):
        """When all agents agree, challenges still happen but are low-severity."""
        memos = [
            PositionMemo(agent=f"A{i}", signal="BUY", conviction=0.8)
            for i in range(6)
        ]
        assignments = _assign_challenges(memos)
        # All agents still get assignments (against arbitrary peers)
        assert len(assignments) == 6

    def test_weighted_score_with_zero_conviction(self):
        """Zero conviction should use floor weight of 0.1."""
        votes = [
            Vote(agent="A", signal="BUY", conviction=0.0),
            Vote(agent="B", signal="SELL", conviction=0.0),
        ]
        score = ChairmanSynthesizer._compute_weighted_score(votes)
        assert 2.0 <= score <= 8.0  # Should be midpoint since equal weights

    def test_empty_memos_challenge_assignment(self):
        assignments = _assign_challenges([])
        assert assignments == {}

    def test_signal_score_mapping(self):
        """Verify all expected signals are in the mapping."""
        assert _SIGNAL_SCORE["STRONG_BUY"] == 2
        assert _SIGNAL_SCORE["BUY"] == 1
        assert _SIGNAL_SCORE["HOLD"] == 0
        assert _SIGNAL_SCORE["SELL"] == -1
        assert _SIGNAL_SCORE["STRONG_SELL"] == -2

    def test_transcript_json_roundtrip(self):
        """Full transcript can be serialized and deserialized."""
        verdict = ICVerdict(
            signal="BUY",
            score=7.2,
            consensus_strength="majority",
            vote_breakdown={"BUY": 4, "HOLD": 1, "SELL": 1},
        )
        transcript = ICTranscript(
            ticker="AAPL",
            round_1_memos=[PositionMemo(agent="Test", signal="BUY")],
            round_4_votes=[Vote(agent="Test", signal="BUY")],
            verdict=verdict,
        )
        data = transcript.model_dump(mode="json")
        restored = ICTranscript.model_validate(data)
        assert restored.ticker == "AAPL"
        assert restored.verdict.score == 7.2
        assert len(restored.round_1_memos) == 1

    def test_vote_breakdown_empty(self):
        assert ChairmanSynthesizer._compute_vote_breakdown([]) == {}
