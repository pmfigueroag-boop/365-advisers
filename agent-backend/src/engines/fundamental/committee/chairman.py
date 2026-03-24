"""
src/engines/fundamental/committee/chairman.py
──────────────────────────────────────────────────────────────────────────────
Chairman synthesis — Round 5 of the Investment Committee simulation.

Takes the full ICTranscript (rounds 1–4) and produces an ICVerdict with:
  - Conviction-weighted vote aggregation
  - Dissent identification and documentation
  - Conviction drift analysis
  - consensus_strength classification
"""

from __future__ import annotations

import logging

from src.engines.fundamental.committee.models import (
    ICTranscript,
    ICVerdict,
    Vote,
)
from src.llm import get_llm, LLMTaskType
from src.utils.helpers import extract_json
from src.utils.language import get_output_language

logger = logging.getLogger("365advisers.engines.fundamental.committee.chairman")

_llm_chairman = get_llm(LLMTaskType.REASONING)

# ─── Signal scoring ──────────────────────────────────────────────────────────

_SIGNAL_NUMERIC: dict[str, float] = {
    "STRONG_BUY": 10.0,
    "BUY": 7.5,
    "HOLD": 5.0,
    "SELL": 2.5,
    "STRONG_SELL": 0.0,
}


class ChairmanSynthesizer:
    """Produces the final ICVerdict from a completed transcript."""

    @staticmethod
    def _compute_vote_breakdown(votes: list[Vote]) -> dict[str, int]:
        tally: dict[str, int] = {}
        for v in votes:
            s = v.signal.upper()
            tally[s] = tally.get(s, 0) + 1
        return tally

    @staticmethod
    def _compute_consensus_strength(votes: list[Vote]) -> str:
        """Classify consensus: unanimous → contested."""
        if not votes:
            return "contested"
        signals = [v.signal.upper() for v in votes]
        unique = set(signals)
        n = len(signals)

        if len(unique) == 1:
            return "unanimous"

        # Count the strongest faction
        from collections import Counter
        counts = Counter(signals)
        top_count = counts.most_common(1)[0][1]

        ratio = top_count / n
        if ratio >= 0.8:
            return "strong_majority"
        if ratio >= 0.6:
            return "majority"
        if ratio >= 0.4:
            return "split"
        return "contested"

    @staticmethod
    def _compute_weighted_score(votes: list[Vote]) -> float:
        """Conviction-weighted average score from votes."""
        total_weight = 0.0
        weighted_sum = 0.0
        for v in votes:
            score = _SIGNAL_NUMERIC.get(v.signal.upper(), 5.0)
            weight = max(0.1, v.conviction)  # floor weight at 0.1
            weighted_sum += score * weight
            weighted_sum_signal = score
            total_weight += weight
        return round(weighted_sum / total_weight, 2) if total_weight > 0 else 5.0

    @staticmethod
    def _derive_consensus_signal(score: float) -> str:
        if score >= 7.5:
            return "STRONG_BUY"
        if score >= 6.0:
            return "BUY"
        if score >= 4.0:
            return "HOLD"
        if score >= 2.5:
            return "SELL"
        return "STRONG_SELL"

    @staticmethod
    def _conviction_drift_summary(votes: list[Vote]) -> str:
        drifts = [v for v in votes if abs(v.conviction_drift) >= 0.05]
        if not drifts:
            return "All agents maintained their initial convictions through the debate."
        parts = []
        for v in drifts:
            direction = "increased" if v.conviction_drift > 0 else "decreased"
            parts.append(
                f"{v.agent} {direction} conviction by {abs(v.conviction_drift):.0%}"
            )
        return "; ".join(parts) + "."

    @classmethod
    def synthesize(cls, ticker: str, transcript: ICTranscript) -> ICVerdict:
        """
        Run the Chairman's LLM synthesis and produce the final ICVerdict.

        Falls back to deterministic aggregation if the LLM call fails.
        """
        votes = transcript.round_4_votes
        vote_breakdown = cls._compute_vote_breakdown(votes)
        consensus_strength = cls._compute_consensus_strength(votes)
        weighted_score = cls._compute_weighted_score(votes)
        signal = cls._derive_consensus_signal(weighted_score)
        drift_summary = cls._conviction_drift_summary(votes)

        # Build dissenting opinions
        dissenting = [v for v in votes if v.dissents]
        dissent_texts = [
            f"{v.agent}: {v.signal} ({v.conviction:.0%}) — {v.rationale}"
            for v in dissenting
        ]

        # ── LLM synthesis ─────────────────────────────────────────────────
        output_lang = get_output_language()
        # Build debate summary for the chairman
        memo_lines = "\n".join(
            f"  {m.agent}: {m.signal} ({m.conviction:.0%}) — {m.thesis[:120]}"
            for m in transcript.round_1_memos
        )
        challenge_lines = "\n".join(
            f"  {c.challenger} → {c.target}: {c.objection[:120]}"
            for c in transcript.round_2_challenges
        )
        rebuttal_lines = "\n".join(
            f"  {r.agent}: {r.defense[:120]}; concession: {r.concession[:80] or 'none'}"
            for r in transcript.round_3_rebuttals
        )
        vote_lines = "\n".join(
            f"  {v.agent}: {v.signal} ({v.conviction:.0%}), drift={v.conviction_drift:+.0%}"
            for v in votes
        )

        prompt = f"""You are the Chairman of an institutional Investment Committee.
You just observed a structured debate on {ticker} with these results:

ROUND 1 — INITIAL POSITIONS:
{memo_lines}

ROUND 2 — CHALLENGES:
{challenge_lines}

ROUND 3 — REBUTTALS:
{rebuttal_lines}

ROUND 4 — FINAL VOTES:
{vote_lines}

COMPUTED METRICS:
- Weighted Score: {weighted_score}/10
- Consensus: {consensus_strength}
- Vote Breakdown: {vote_breakdown}
- Conviction Drift: {drift_summary}

TASK: Write a Chairman's synthesis paragraph in {output_lang}.
Integrate the debate dynamics—who shifted, what challenges were decisive.
The final signal MUST be {signal} (derived from conviction-weighted votes).

Respond ONLY with valid JSON:
{{
  "narrative": "<3-5 sentence institutional synthesis in {output_lang}>",
  "key_catalysts": ["<catalyst1>", "<catalyst2>"],
  "key_risks": ["<risk1>", "<risk2>"]
}}"""

        narrative = ""
        catalysts: list[str] = []
        risks: list[str] = []

        try:
            from src.observability import traced_llm_call
            result = traced_llm_call("gemini-2.5-pro", prompt, _llm_chairman.invoke)
            parsed = extract_json(result.content)
            if parsed:
                narrative = str(parsed.get("narrative", ""))
                catalysts = list(parsed.get("key_catalysts", []))
                risks = list(parsed.get("key_risks", []))
        except Exception as exc:
            logger.error(f"Chairman LLM synthesis failed for {ticker}: {exc}")

        if not narrative:
            narrative = (
                f"The Investment Committee reached a {consensus_strength.replace('_', ' ')} "
                f"consensus of {signal} on {ticker} with a weighted score of "
                f"{weighted_score}/10. {drift_summary}"
            )

        # Compute overall confidence from vote convictions
        avg_conviction = (
            sum(v.conviction for v in votes) / len(votes) if votes else 0.5
        )

        return ICVerdict(
            signal=signal,
            score=weighted_score,
            confidence=round(avg_conviction, 2),
            consensus_strength=consensus_strength,
            narrative=narrative,
            key_catalysts=catalysts,
            key_risks=risks,
            dissenting_opinions=dissent_texts,
            conviction_drift_summary=drift_summary,
            vote_breakdown=vote_breakdown,
        )
