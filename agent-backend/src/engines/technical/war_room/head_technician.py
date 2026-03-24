"""
src/engines/technical/war_room/head_technician.py
──────────────────────────────────────────────────────────────────────────────
Round 5 synthesis — the Head Technician produces the final verdict.

Conviction-weighted vote aggregation, consensus classification, action plan
generation, and executive narrative synthesis.
"""

from __future__ import annotations

import logging

from src.engines.technical.war_room.models import (
    TacticalVote,
    TechnicalICTranscript,
    TechnicalICVerdict,
    ActionPlan,
)
from src.utils.helpers import extract_json
from src.llm import get_llm, LLMTaskType
from src.utils.language import get_output_language

logger = logging.getLogger("365advisers.engines.technical.war_room.head_technician")


# ─── Signal scoring — homologated with IC Debate (0-10 scale) ────────────────

_SIGNAL_SCORE: dict[str, float] = {
    "STRONG_BULLISH": 10.0,
    "BULLISH": 7.5,
    "NEUTRAL": 5.0,
    "BEARISH": 2.5,
    "STRONG_BEARISH": 0.0,
}


class HeadTechnicianSynthesizer:
    """Synthesize the War Room debate into a final verdict."""

    @staticmethod
    def synthesize(
        ticker: str,
        transcript: TechnicalICTranscript,
    ) -> TechnicalICVerdict:
        votes = transcript.round_4_votes
        if not votes:
            return TechnicalICVerdict(
                signal="NEUTRAL",
                score=5.0,
                confidence=0.5,
                consensus_strength="contested",
                narrative=f"No votes available for {ticker}.",
            )

        # ── Conviction×regime-weighted vote aggregation (0-10 scale) ──
        weighted_score = 0.0
        total_weight = 0.0
        vote_tally: dict[str, int] = {}

        for vote in votes:
            weight = max(0.1, vote.conviction) * vote.regime_weight
            signal_val = _SIGNAL_SCORE.get(vote.signal.upper(), 5.0)
            weighted_score += signal_val * weight
            total_weight += weight
            key = vote.signal.upper()
            vote_tally[key] = vote_tally.get(key, 0) + 1

        score = round(weighted_score / total_weight, 2) if total_weight > 0 else 5.0

        logger.info(
            f"TechIC [{ticker}] Score computation: "
            + " | ".join(
                f"{v.agent}: {v.signal}(val={_SIGNAL_SCORE.get(v.signal.upper(), 5.0)}) "
                f"conv={v.conviction:.0%} rw={v.regime_weight:.1f} "
                f"→ w={max(0.1, v.conviction) * v.regime_weight:.2f}"
                for v in votes
            )
            + f" || SCORE={score}/10"
        )

        # ── Derive signal from score (narrowed NEUTRAL band: 4.5–5.5) ──
        if score >= 7.5:
            final_signal = "STRONG_BUY"
        elif score >= 5.5:
            final_signal = "BUY"
        elif score <= 2.5:
            final_signal = "STRONG_SELL"
        elif score <= 4.5:
            final_signal = "SELL"
        else:
            final_signal = "NEUTRAL"

        # ── Confidence ───────────────────────────────────────────
        avg_conviction = sum(v.conviction for v in votes) / len(votes) if votes else 0.5

        # ── Consensus strength ──────────────────────────────────
        max_vote = max(vote_tally.values()) if vote_tally else 0
        total_votes = len(votes)
        dissenters = [v for v in votes if v.dissents]

        if max_vote == total_votes:
            consensus = "unanimous"
        elif max_vote >= total_votes * 0.8:
            consensus = "strong_majority"
        elif max_vote >= total_votes * 0.5:
            consensus = "majority"
        elif len(dissenters) >= total_votes * 0.4:
            consensus = "contested"
        else:
            consensus = "split"

        # ── Dissenting opinions ──────────────────────────────────
        dissenting = [
            f"{v.agent}: {v.signal} (conviction={v.conviction:.0%}) — {v.rationale}"
            for v in votes if v.dissents
        ]

        # ── LLM narrative synthesis ──────────────────────────────
        narrative, action_plan, key_levels, timing, risk_factors = (
            _generate_narrative(ticker, transcript, final_signal, avg_conviction,
                                consensus)
        )

        return TechnicalICVerdict(
            signal=final_signal,
            score=score,
            confidence=round(avg_conviction, 2),
            consensus_strength=consensus,
            narrative=narrative,
            action_plan=action_plan,
            key_levels=key_levels,
            timing=timing,
            risk_factors=risk_factors,
            vote_breakdown=vote_tally,
            dissenting_opinions=dissenting,
        )


def _generate_narrative(
    ticker: str,
    transcript: TechnicalICTranscript,
    final_signal: str,
    confidence: float,
    consensus: str,
) -> tuple[str, ActionPlan, str, str, list[str]]:
    """Use LLM to generate the executive narrative and action plan."""
    lang = get_output_language()

    # Build debate summary for the prompt
    assess_lines = "\n".join(
        f"  - {a.agent} ({a.domain}): {a.signal} conv={a.conviction:.0%} — {a.thesis[:120]}"
        for a in transcript.round_1_assessments
    )
    conflict_lines = "\n".join(
        f"  - {c.challenger} challenges {c.target} ({c.severity}): {c.disagreement[:100]}"
        for c in transcript.round_2_conflicts
    )
    tf_lines = "\n".join(
        f"  - {t.agent}: alignment={t.timeframe_alignment}, dominant_tf={t.dominant_timeframe}, adj={t.conviction_adjustment:+.2f}"
        for t in transcript.round_3_timeframes
    )
    vote_lines = "\n".join(
        f"  - {v.agent}: {v.signal} conv={v.conviction:.0%} drift={v.conviction_drift:+.2f} {'\u26a0\ufe0f DISSENT' if v.dissents else ''}"
        for v in transcript.round_4_votes
    )

    json_template = (
        '{\n'
        '  "narrative": "<3-5 sentences synthesizing the debate: where analysts agreed, where they diverged, what the data says. Institutional tone.>",\n'
        '  "action_plan": {\n'
        '    "entry_zone": "<price range or condition>",\n'
        '    "stop_loss": "<level + rationale>",\n'
        '    "take_profit_1": "<nearest target>",\n'
        '    "take_profit_2": "<extended target>",\n'
        '    "invalidation": "<scenario that would kill the trade>",\n'
        '    "risk_reward": "<e.g., 1:2.4>",\n'
        '    "position_size_note": "<e.g., Full position — strong consensus and low vol regime>"\n'
        '  },\n'
        '  "key_levels": "<key S/R levels with theoretical context>",\n'
        '  "timing": "<entry timing recommendation>",\n'
        '  "risk_factors": ["<risk 1 citing data>", "<risk 2>", "<risk 3>"]\n'
        '}'
    )

    prompt = f"""You are the Head Technician synthesizing the War Room debate on {ticker}.

DEBATE SUMMARY:
Final Signal: {final_signal} | Confidence: {confidence:.0%} | Consensus: {consensus}

Round 1 Assessments:
{assess_lines}

Round 2 Conflicts:
{conflict_lines}

Round 3 Timeframe Reconciliation:
{tf_lines}

Round 4 Votes:
{vote_lines}

TASK: Produce the executive synthesis. Be specific, cite data from the debate.
The conclusion is derived entirely from the War Room's deliberation — no external engine reference.

Respond ONLY with valid JSON. ALL text in {lang}.
{json_template}"""

    parsed = _invoke_llm_for_synthesis(prompt)

    if not parsed:
        return (
            f"War Room {consensus} {final_signal} for {ticker}.",
            ActionPlan(),
            "Key levels unavailable.",
            "Timing analysis unavailable.",
            ["Detailed risk analysis unavailable."],
        )

    ap_data = parsed.get("action_plan", {})
    action_plan = ActionPlan(
        entry_zone=str(ap_data.get("entry_zone", "")),
        stop_loss=str(ap_data.get("stop_loss", "")),
        take_profit_1=str(ap_data.get("take_profit_1", "")),
        take_profit_2=str(ap_data.get("take_profit_2", "")),
        invalidation=str(ap_data.get("invalidation", "")),
        risk_reward=str(ap_data.get("risk_reward", "")),
        position_size_note=str(ap_data.get("position_size_note", "")),
    )

    return (
        str(parsed.get("narrative", "")),
        action_plan,
        str(parsed.get("key_levels", "")),
        str(parsed.get("timing", "")),
        list(parsed.get("risk_factors", [])),
    )


# LLM instance for synthesis — use reasoning model (same as IC Chairman)
_llm_synthesis = get_llm(LLMTaskType.REASONING)


def _invoke_llm_for_synthesis(prompt: str) -> dict:
    """Call LLM and parse JSON for Head Technician synthesis."""
    try:
        from src.observability import traced_llm_call
        result = traced_llm_call("gemini-2.5-pro", prompt, _llm_synthesis.invoke)
        raw = result.content if hasattr(result, "content") else str(result)
        parsed = extract_json(raw)
        if parsed:
            return parsed
        logger.warning("Head Technician: could not parse LLM response")
        return {}
    except Exception as exc:
        logger.error(f"Head Technician LLM failed: {exc}")
        return {}
