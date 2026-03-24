"""
src/engines/technical/war_room/debate.py
──────────────────────────────────────────────────────────────────────────────
5-round debate orchestrator for the Technical IC War Room.

Orchestrates:
  Round 1 — ASSESS:     All 6 agents state initial positions
  Round 2 — CONFLICT:   Maximum-disagreement conflict identification
  Round 3 — TIMEFRAME:  Multi-timeframe reconciliation + challenge defense
  Round 4 — CONVICTION: Final votes with regime-weighted influence
  Round 5 — SYNTHESIS:  Head Technician produces verdict + action plan
"""

from __future__ import annotations

import asyncio
import logging
import time as _time
from typing import AsyncIterator, Any

from src.engines.technical.war_room.models import (
    TacticalMember,
    TacticalAssessment,
    TacticalConflict,
    TimeframeAssessment,
    TacticalVote,
    TechnicalICTranscript,
    TechnicalICVerdict,
)
from src.engines.technical.war_room import agents as agent_module
from src.engines.technical.war_room.head_technician import HeadTechnicianSynthesizer

logger = logging.getLogger("365advisers.engines.technical.war_room.debate")

# ─── Signal direction for disagreement scoring ──────────────────────────────

_SIGNAL_SCORE: dict[str, float] = {
    "STRONG_BULLISH": 10.0,
    "BULLISH": 7.5,
    "NEUTRAL": 5.0,
    "BEARISH": 2.5,
    "STRONG_BEARISH": 0.0,
}

# ─── Regime-based agent weights ─────────────────────────────────────────────
# In a TRENDING regime the Trend Strategist's vote carries more weight, etc.

REGIME_AGENT_WEIGHTS: dict[str, dict[str, float]] = {
    "TRENDING": {
        "Trend Strategist": 1.4, "Momentum Analyst": 1.0,
        "Volatility Analyst": 0.8, "Volume/Flow Specialist": 1.0,
        "Structure Analyst": 0.7, "MTF Specialist": 1.1,
    },
    "RANGING": {
        "Trend Strategist": 0.7, "Momentum Analyst": 1.3,
        "Volatility Analyst": 1.0, "Volume/Flow Specialist": 1.0,
        "Structure Analyst": 1.3, "MTF Specialist": 1.0,
    },
    "VOLATILE": {
        "Trend Strategist": 0.9, "Momentum Analyst": 0.9,
        "Volatility Analyst": 1.4, "Volume/Flow Specialist": 1.1,
        "Structure Analyst": 0.8, "MTF Specialist": 1.0,
    },
    "TRANSITIONING": {
        "Trend Strategist": 1.0, "Momentum Analyst": 1.0,
        "Volatility Analyst": 1.0, "Volume/Flow Specialist": 1.0,
        "Structure Analyst": 1.0, "MTF Specialist": 1.0,
    },
}


def _disagreement(a: TacticalAssessment, b: TacticalAssessment) -> float:
    """Compute disagreement between two assessments (higher = more opposed)."""
    dir_a = _SIGNAL_SCORE.get(a.signal.upper(), 0)
    dir_b = _SIGNAL_SCORE.get(b.signal.upper(), 0)
    signal_dist = abs(dir_a - dir_b)
    conviction_boost = (a.conviction + b.conviction) / 2.0
    return signal_dist + conviction_boost * 0.3


def _assign_conflicts(assessments: list[TacticalAssessment]) -> dict[str, str]:
    """
    Maximum-disagreement conflict assignment.
    Each agent challenges the peer whose assessment opposes theirs the most.
    Returns {challenger_name: target_name}.
    """
    assignments: dict[str, str] = {}
    for assess in assessments:
        best_target = None
        best_score = -1.0
        for other in assessments:
            if other.agent == assess.agent:
                continue
            score = _disagreement(assess, other)
            if score > best_score:
                best_score = score
                best_target = other.agent
        if best_target:
            assignments[assess.agent] = best_target
    return assignments


class TechnicalWarRoom:
    """
    Orchestrates the full Technical IC simulation.

    Can run synchronously (returning the complete transcript) or as an
    async generator (yielding SSE-ready events at each round).
    """

    def __init__(self, members: list[TacticalMember] | None = None):
        self.members = members or agent_module.WAR_ROOM_MEMBERS

    async def run_full(
        self,
        ticker: str,
        engine_data: dict[str, Any],
    ) -> TechnicalICTranscript:
        """Run the complete 5-round debate and return the transcript."""
        transcript = TechnicalICTranscript(ticker=ticker, members=self.members)
        start_ms = _time.monotonic_ns() / 1e6
        regime = engine_data.get("regime", {}).get("trend_regime", "TRANSITIONING")

        # Round 1
        assessments = await self._round_assess(ticker, engine_data)
        transcript.round_1_assessments = assessments

        # Round 2
        conflicts = await self._round_conflict(ticker, assessments)
        transcript.round_2_conflicts = conflicts

        # Round 3
        timeframes = await self._round_timeframe(
            ticker, assessments, conflicts,
            engine_data.get("mtf_data"),
        )
        transcript.round_3_timeframes = timeframes

        # Round 4
        votes = self._round_conviction(assessments, timeframes, regime)
        transcript.round_4_votes = votes

        # Round 5
        verdict = await asyncio.to_thread(
            HeadTechnicianSynthesizer.synthesize,
            ticker, transcript,
        )
        transcript.verdict = verdict
        transcript.elapsed_ms = round(_time.monotonic_ns() / 1e6 - start_ms)

        return transcript

    async def run_stream(
        self,
        ticker: str,
        engine_data: dict[str, Any],
    ) -> AsyncIterator[dict]:
        """
        Async generator yielding SSE-ready events at each round.

        Events:
          tic_members         — list of War Room member identities
          tic_round_assess    — each agent's assessment (×6)
          tic_round_conflict  — each conflict (×6)
          tic_round_timeframe — each timeframe assessment
          tic_round_vote      — each vote (×6)
          tic_verdict         — Head Technician's final synthesis
          tic_done            — end marker
        """
        start_ms = _time.monotonic_ns() / 1e6
        transcript = TechnicalICTranscript(ticker=ticker, members=self.members)
        regime = engine_data.get("regime", {}).get("trend_regime", "TRANSITIONING")

        # Emit members
        yield {
            "event": "tic_members",
            "data": {
                "members": [m.model_dump() for m in self.members],
                "ticker": ticker,
            },
        }
        await asyncio.sleep(0)

        # Round 1: Assess
        logger.info(f"TechIC [{ticker}] Round 1: ASSESS")
        assessments = await self._round_assess(ticker, engine_data)
        transcript.round_1_assessments = assessments
        for a in assessments:
            yield {"event": "tic_round_assess", "data": a.model_dump()}
            await asyncio.sleep(0)

        # Round 2: Conflict
        logger.info(f"TechIC [{ticker}] Round 2: CONFLICT")
        conflicts = await self._round_conflict(ticker, assessments)
        transcript.round_2_conflicts = conflicts
        for c in conflicts:
            yield {"event": "tic_round_conflict", "data": c.model_dump()}
            await asyncio.sleep(0)

        # Round 3: Timeframe
        logger.info(f"TechIC [{ticker}] Round 3: TIMEFRAME")
        timeframes = await self._round_timeframe(
            ticker, assessments, conflicts,
            engine_data.get("mtf_data"),
        )
        transcript.round_3_timeframes = timeframes
        for t in timeframes:
            yield {"event": "tic_round_timeframe", "data": t.model_dump()}
            await asyncio.sleep(0)

        # Round 4: Conviction
        logger.info(f"TechIC [{ticker}] Round 4: CONVICTION")
        votes = self._round_conviction(assessments, timeframes, regime)
        transcript.round_4_votes = votes
        for v in votes:
            yield {"event": "tic_round_vote", "data": v.model_dump()}
            await asyncio.sleep(0)

        # Round 5: Head Technician Synthesis
        logger.info(f"TechIC [{ticker}] Round 5: SYNTHESIS")
        verdict = await asyncio.to_thread(
            HeadTechnicianSynthesizer.synthesize,
            ticker, transcript,
        )
        transcript.verdict = verdict
        transcript.elapsed_ms = round(_time.monotonic_ns() / 1e6 - start_ms)

        yield {"event": "tic_verdict", "data": verdict.model_dump()}
        yield {
            "event": "tic_done",
            "data": {"elapsed_ms": transcript.elapsed_ms, "ticker": ticker},
        }

    # ─── Round implementations ────────────────────────────────────────────

    async def _round_assess(
        self, ticker: str, engine_data: dict[str, Any],
    ) -> list[TacticalAssessment]:
        """Round 1: all agents assess in parallel."""
        tasks = [
            asyncio.to_thread(agent_module.assess, member, ticker, engine_data)
            for member in self.members
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assessments: list[TacticalAssessment] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Assess failed for {self.members[i].name}: {result}")
            elif result is None:
                logger.warning(f"{self.members[i].name} did not participate (LLM failure).")
            else:
                assessments.append(result)
        logger.info(f"TechIC: {len(assessments)}/{len(self.members)} agents participated in R1.")
        return assessments

    async def _round_conflict(
        self, ticker: str, assessments: list[TacticalAssessment],
    ) -> list[TacticalConflict]:
        """Round 2: maximum-disagreement conflict identification."""
        assignments = _assign_conflicts(assessments)
        assess_by_name = {a.agent: a for a in assessments}
        member_by_name = {m.name: m for m in self.members}

        tasks = []
        for challenger_name, target_name in assignments.items():
            member = member_by_name.get(challenger_name)
            own = assess_by_name.get(challenger_name)
            target = assess_by_name.get(target_name)
            if member and own and target:
                tasks.append(
                    asyncio.to_thread(
                        agent_module.challenge, member, own, target, ticker
                    )
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        conflicts: list[TacticalConflict] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Conflict failed: {result}")
            elif result is not None:
                conflicts.append(result)
        return conflicts

    async def _round_timeframe(
        self,
        ticker: str,
        assessments: list[TacticalAssessment],
        conflicts: list[TacticalConflict],
        mtf_data: dict[str, Any] | None = None,
    ) -> list[TimeframeAssessment]:
        """Round 3: multi-timeframe reconciliation + challenge defense."""
        # Group challenges by target
        challenges_by_target: dict[str, list[TacticalConflict]] = {}
        for c in conflicts:
            challenges_by_target.setdefault(c.target, []).append(c)

        assess_by_name = {a.agent: a for a in assessments}
        member_by_name = {m.name: m for m in self.members}

        tasks = []
        for member in self.members:
            own = assess_by_name.get(member.name)
            received = challenges_by_target.get(member.name, [])
            if own:
                tasks.append(
                    asyncio.to_thread(
                        agent_module.reconcile_timeframes,
                        member, own, received, ticker, mtf_data,
                    )
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        timeframes: list[TimeframeAssessment] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Timeframe reconciliation failed: {result}")
            elif result is not None:
                timeframes.append(result)
        return timeframes

    def _round_conviction(
        self,
        assessments: list[TacticalAssessment],
        timeframes: list[TimeframeAssessment],
        regime: str = "TRANSITIONING",
    ) -> list[TacticalVote]:
        """
        Round 4: final votes with regime-weighted influence.
        Computed locally (no LLM call) from assessment + timeframe adjustments.
        """
        assess_by_name = {a.agent: a for a in assessments}
        tf_by_name = {t.agent: t for t in timeframes}
        regime_weights = REGIME_AGENT_WEIGHTS.get(
            regime, REGIME_AGENT_WEIGHTS["TRANSITIONING"]
        )

        # Determine emerging majority signal
        signal_tally: dict[str, int] = {}
        for a in assessments:
            s = a.signal.upper()
            signal_tally[s] = signal_tally.get(s, 0) + 1
        majority_signal = max(signal_tally, key=signal_tally.get) if signal_tally else "NEUTRAL"

        votes: list[TacticalVote] = []
        for member in agent_module.WAR_ROOM_MEMBERS:
            assess = assess_by_name.get(member.name)
            tf = tf_by_name.get(member.name)

            if not assess:
                # Agent did not participate in R1 → skip, don't inject phantom vote
                logger.info(f"TechIC R4: {member.name} skipped (no R1 assessment).")
                continue

            # Adjust conviction from timeframe reconciliation
            adj = tf.conviction_adjustment if tf else 0.0
            final_conviction = min(1.0, max(0.0, assess.conviction + adj))
            drift = final_conviction - assess.conviction

            # If conviction drops significantly, may shift to NEUTRAL
            final_signal = assess.signal
            if final_conviction < 0.3 and assess.signal in (
                "STRONG_BULLISH", "BULLISH", "BEARISH", "STRONG_BEARISH"
            ):
                final_signal = "NEUTRAL"

            # Detect dissent (bullish vs bearish direction)
            final_val = _SIGNAL_SCORE.get(final_signal.upper(), 5.0)
            majority_val = _SIGNAL_SCORE.get(majority_signal.upper(), 5.0)
            dissents = (final_val > 5.0 and majority_val < 5.0) or (final_val < 5.0 and majority_val > 5.0)

            # Regime weight
            rw = regime_weights.get(member.name, 1.0)

            votes.append(TacticalVote(
                agent=member.name,
                signal=final_signal,
                conviction=round(final_conviction, 2),
                conviction_drift=round(drift, 2),
                rationale=f"{'Maintained' if abs(drift) < 0.05 else 'Adjusted'} position after timeframe reconciliation.",
                regime_weight=rw,
                dissents=dissents,
            ))

        return votes
