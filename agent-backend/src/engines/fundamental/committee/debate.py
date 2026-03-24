"""
src/engines/fundamental/committee/debate.py
──────────────────────────────────────────────────────────────────────────────
Multi-round deliberation engine for the Investment Committee simulation.

Orchestrates the 5-round debate sequence:
  Round 1 — PRESENT:   All agents state initial positions
  Round 2 — CHALLENGE: Maximum-disagreement challenge assignment
  Round 3 — REBUT:     Challenged agents defend
  Round 4 — VOTE:      All agents cast final votes
  Round 5 — SYNTHESIS: Chairman produces ICVerdict
"""

from __future__ import annotations

import asyncio
import logging
import time as _time
from datetime import datetime, timezone
from typing import AsyncIterator

from src.engines.fundamental.committee.models import (
    ICMember,
    ICTranscript,
    ICVerdict,
    PositionMemo,
    Challenge,
    Rebuttal,
    Vote,
)
from src.engines.fundamental.committee import agents as agent_module
from src.engines.fundamental.committee.chairman import ChairmanSynthesizer

logger = logging.getLogger("365advisers.engines.fundamental.committee.debate")

# ─── Signal direction mapping ────────────────────────────────────────────────

_SIGNAL_SCORE: dict[str, int] = {
    "STRONG_BUY": 2,
    "BUY": 1,
    "HOLD": 0,
    "SELL": -1,
    "STRONG_SELL": -2,
}


def _disagreement(a: PositionMemo, b: PositionMemo) -> float:
    """Compute disagreement score between two memos (higher = more opposed)."""
    dir_a = _SIGNAL_SCORE.get(a.signal.upper(), 0)
    dir_b = _SIGNAL_SCORE.get(b.signal.upper(), 0)
    signal_dist = abs(dir_a - dir_b)
    conviction_boost = (a.conviction + b.conviction) / 2.0
    return signal_dist + conviction_boost * 0.5


def _assign_challenges(memos: list[PositionMemo]) -> dict[str, str]:
    """
    Maximum-disagreement challenge assignment.
    Each agent challenges the peer whose position opposes theirs the most.
    Returns {challenger_name: target_name}.
    """
    memo_by_name = {m.agent: m for m in memos}
    assignments: dict[str, str] = {}

    for memo in memos:
        best_target = None
        best_score = -1.0
        for other in memos:
            if other.agent == memo.agent:
                continue
            score = _disagreement(memo, other)
            if score > best_score:
                best_score = score
                best_target = other.agent
        if best_target:
            assignments[memo.agent] = best_target

    return assignments


class InvestmentCommitteeDebate:
    """
    Orchestrates the full IC simulation.

    Can run synchronously (returning the complete transcript) or as an
    async generator (yielding SSE-ready events at each round).
    """

    def __init__(self, members: list[ICMember] | None = None):
        self.members = members or agent_module.IC_MEMBERS

    async def run_full(
        self,
        ticker: str,
        financial_data: dict,
    ) -> ICTranscript:
        """Run the complete 5-round debate and return the transcript."""
        transcript = ICTranscript(ticker=ticker, members=self.members)
        start_ms = _time.monotonic_ns() / 1e6

        # Round 1: Present
        memos = await self._round_present(ticker, financial_data)
        transcript.round_1_memos = memos

        # Round 2: Challenge
        challenges = await self._round_challenge(ticker, memos)
        transcript.round_2_challenges = challenges

        # Round 3: Rebut
        rebuttals = await self._round_rebut(ticker, memos, challenges)
        transcript.round_3_rebuttals = rebuttals

        # Round 4: Vote
        votes = await self._round_vote(ticker, memos, challenges, rebuttals)
        transcript.round_4_votes = votes

        # Round 5: Chairman synthesis
        verdict = await asyncio.to_thread(
            ChairmanSynthesizer.synthesize, ticker, transcript
        )
        transcript.verdict = verdict
        transcript.elapsed_ms = round(_time.monotonic_ns() / 1e6 - start_ms)

        return transcript

    async def run_stream(
        self,
        ticker: str,
        financial_data: dict,
    ) -> AsyncIterator[dict]:
        """
        Async generator yielding SSE-ready events at each round.

        Events:
          ic_members        — list of IC member identities
          ic_round_present  — each agent's memo (×6)
          ic_round_challenge— each challenge (×6)
          ic_round_rebuttal — each rebuttal
          ic_round_vote     — each vote (×6)
          ic_verdict        — chairman's final synthesis
          ic_done           — end marker
        """
        start_ms = _time.monotonic_ns() / 1e6
        transcript = ICTranscript(ticker=ticker, members=self.members)

        # Emit members
        yield {
            "event": "ic_members",
            "data": {
                "members": [m.model_dump() for m in self.members],
                "ticker": ticker,
            },
        }
        await asyncio.sleep(0)

        # Round 1: Present
        logger.info(f"IC [{ticker}] Round 1: PRESENT")
        memos = await self._round_present(ticker, financial_data)
        transcript.round_1_memos = memos
        for memo in memos:
            yield {"event": "ic_round_present", "data": memo.model_dump()}
            await asyncio.sleep(0)

        # Round 2: Challenge
        logger.info(f"IC [{ticker}] Round 2: CHALLENGE")
        challenges = await self._round_challenge(ticker, memos)
        transcript.round_2_challenges = challenges
        for ch in challenges:
            yield {"event": "ic_round_challenge", "data": ch.model_dump()}
            await asyncio.sleep(0)

        # Round 3: Rebut
        logger.info(f"IC [{ticker}] Round 3: REBUT")
        rebuttals = await self._round_rebut(ticker, memos, challenges)
        transcript.round_3_rebuttals = rebuttals
        for reb in rebuttals:
            yield {"event": "ic_round_rebuttal", "data": reb.model_dump()}
            await asyncio.sleep(0)

        # Round 4: Vote
        logger.info(f"IC [{ticker}] Round 4: VOTE")
        votes = await self._round_vote(ticker, memos, challenges, rebuttals)
        transcript.round_4_votes = votes
        for vote in votes:
            yield {"event": "ic_round_vote", "data": vote.model_dump()}
            await asyncio.sleep(0)

        # Round 5: Chairman synthesis
        logger.info(f"IC [{ticker}] Round 5: CHAIRMAN SYNTHESIS")
        verdict = await asyncio.to_thread(
            ChairmanSynthesizer.synthesize, ticker, transcript
        )
        transcript.verdict = verdict
        transcript.elapsed_ms = round(_time.monotonic_ns() / 1e6 - start_ms)

        yield {"event": "ic_verdict", "data": verdict.model_dump()}
        yield {
            "event": "ic_done",
            "data": {"elapsed_ms": transcript.elapsed_ms, "ticker": ticker},
        }

    # ─── Round implementations ────────────────────────────────────────────

    async def _round_present(
        self, ticker: str, financial_data: dict
    ) -> list[PositionMemo]:
        """Run Round 1: all agents present in parallel."""
        tasks = [
            asyncio.to_thread(agent_module.present, member, ticker, financial_data)
            for member in self.members
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        memos: list[PositionMemo] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Present failed for {self.members[i].name}: {result}")
                memos.append(PositionMemo(
                    agent=self.members[i].name, signal="HOLD", conviction=0.5,
                    thesis=f"{self.members[i].name} could not present.",
                ))
            else:
                memos.append(result)
        return memos

    async def _round_challenge(
        self, ticker: str, memos: list[PositionMemo]
    ) -> list[Challenge]:
        """Run Round 2: maximum-disagreement challenge assignment."""
        assignments = _assign_challenges(memos)
        memo_by_name = {m.agent: m for m in memos}
        member_by_name = {m.name: m for m in self.members}

        tasks = []
        for challenger_name, target_name in assignments.items():
            member = member_by_name.get(challenger_name)
            own_memo = memo_by_name.get(challenger_name)
            target_memo = memo_by_name.get(target_name)
            if member and own_memo and target_memo:
                tasks.append(
                    asyncio.to_thread(
                        agent_module.challenge, member, own_memo, target_memo, ticker
                    )
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        challenges: list[Challenge] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Challenge failed: {result}")
            else:
                challenges.append(result)
        return challenges

    async def _round_rebut(
        self,
        ticker: str,
        memos: list[PositionMemo],
        challenges: list[Challenge],
    ) -> list[Rebuttal]:
        """Run Round 3: challenged agents defend."""
        # Group challenges by target
        challenges_by_target: dict[str, list[Challenge]] = {}
        for ch in challenges:
            challenges_by_target.setdefault(ch.target, []).append(ch)

        memo_by_name = {m.agent: m for m in memos}
        member_by_name = {m.name: m for m in self.members}

        tasks = []
        for target_name, target_challenges in challenges_by_target.items():
            member = member_by_name.get(target_name)
            memo = memo_by_name.get(target_name)
            if member and memo:
                tasks.append(
                    asyncio.to_thread(
                        agent_module.rebut, member, memo, target_challenges, ticker
                    )
                )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        rebuttals: list[Rebuttal] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Rebuttal failed: {result}")
            else:
                rebuttals.append(result)
        return rebuttals

    async def _round_vote(
        self,
        ticker: str,
        memos: list[PositionMemo],
        challenges: list[Challenge],
        rebuttals: list[Rebuttal],
    ) -> list[Vote]:
        """
        Run Round 4: all agents cast final votes.

        Vote is computed locally (no extra LLM call) by adjusting initial
        conviction based on rebuttal concessions.
        """
        memo_by_name = {m.agent: m for m in memos}
        rebuttal_by_agent = {r.agent: r for r in rebuttals}

        # Determine emerging majority signal
        signal_tally: dict[str, int] = {}
        for memo in memos:
            s = memo.signal.upper()
            signal_tally[s] = signal_tally.get(s, 0) + 1
        majority_signal = max(signal_tally, key=signal_tally.get) if signal_tally else "HOLD"

        votes: list[Vote] = []
        for member in self.members:
            memo = memo_by_name.get(member.name)
            if not memo:
                votes.append(Vote(agent=member.name, signal="HOLD", conviction=0.5))
                continue

            # Adjust conviction based on rebuttal
            rebuttal = rebuttal_by_agent.get(member.name)
            adj = rebuttal.conviction_adjustment if rebuttal else 0.0
            final_conviction = min(1.0, max(0.0, memo.conviction + adj))
            drift = final_conviction - memo.conviction

            # If conviction dropped significantly, may shift to HOLD
            final_signal = memo.signal
            if final_conviction < 0.3 and memo.signal in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL"):
                final_signal = "HOLD"

            # Detect dissent
            final_dir = _SIGNAL_SCORE.get(final_signal.upper(), 0)
            majority_dir = _SIGNAL_SCORE.get(majority_signal.upper(), 0)
            dissents = (final_dir > 0 and majority_dir < 0) or (final_dir < 0 and majority_dir > 0)

            votes.append(Vote(
                agent=member.name,
                signal=final_signal,
                conviction=round(final_conviction, 2),
                rationale=f"{'Maintained' if abs(drift) < 0.05 else 'Adjusted'} position after debate.",
                dissents=dissents,
                conviction_drift=round(drift, 2),
            ))

        return votes
