"""
src/engines/fundamental/committee/agents.py
──────────────────────────────────────────────────────────────────────────────
Six Investment Committee member agents, each with a distinct persona.

Each agent can: present(), challenge(), rebut().
All LLM calls go through the platform's standard LLM subsystem.
"""

from __future__ import annotations

import logging
from typing import Any

from src.engines.fundamental.committee.models import (
    ICMember,
    PositionMemo,
    Challenge,
    Rebuttal,
)
from src.llm import get_llm, LLMTaskType
from src.utils.helpers import extract_json
from src.utils.language import get_output_language

logger = logging.getLogger("365advisers.engines.fundamental.committee.agents")

# ─── LLM instances ───────────────────────────────────────────────────────────

_llm_agent = get_llm(LLMTaskType.FAST)


# ─── IC Member Definitions ───────────────────────────────────────────────────

IC_MEMBERS: list[ICMember] = [
    ICMember(
        name="Value Analyst",
        role="Senior Equity Analyst — Value & MoS",
        framework="Benjamin Graham / Warren Buffett — Intrinsic Value, DCF, Margin of Safety",
        bias="Favours cheap stocks; sceptical of growth stories without earnings power",
    ),
    ICMember(
        name="Quality Analyst",
        role="Head of Equity Research — Quality & Moat",
        framework="Charlie Munger / Phil Fisher — Durable Competitive Advantage, ROIC",
        bias="Favours high-ROIC businesses; dismisses capital-intensive, low-margin companies",
    ),
    ICMember(
        name="Capital Steward",
        role="Director of Capital Allocation — Activist Lens",
        framework="Carl Icahn / Activist — FCF deployment, buybacks, leverage discipline",
        bias="Focuses on shareholder returns; sceptical of acquisition-driven growth",
    ),
    ICMember(
        name="Risk Officer",
        role="Chief Risk Officer — Downside & Tail Risk",
        framework="Howard Marks / Ray Dalio — Cycle positioning, tail risk, leverage stress",
        bias="Default sceptic; always stress-tests the bull case",
    ),
    ICMember(
        name="Growth Strategist",
        role="Portfolio Strategist — Growth & Momentum",
        framework="Peter Lynch / T. Rowe Price — PEG, earnings runway, secular trends",
        bias="Favours growth companies; willing to pay premium for runway",
    ),
    ICMember(
        name="Macro Strategist",
        role="Chief Macro Strategist — Rates, Regime & Flows",
        framework="Ray Dalio / George Soros — Macro regime, credit cycle, liquidity",
        bias="Top-down thinker; may override bottom-up thesis on macro grounds",
    ),
]


# ─── Agent Methods ────────────────────────────────────────────────────────────


def _invoke_llm(prompt: str) -> dict | None:
    """Safe LLM call with JSON extraction."""
    try:
        from src.observability import traced_llm_call
        result = traced_llm_call("gemini-2.5-flash", prompt, _llm_agent.invoke)
        return extract_json(result.content)
    except Exception as exc:
        logger.error(f"IC Agent LLM error: {exc}")
        return None


def present(member: ICMember, ticker: str, data: dict) -> PositionMemo:
    """Round 1: Agent presents their initial position memo."""
    output_lang = get_output_language()
    prompt = f"""You are {member.name}, a {member.role} on an Investment Committee.
Your framework: {member.framework}
Known analytical bias: {member.bias}

COMPANY: {ticker}
FINANCIAL DATA:
{data}

TASK: Present your initial investment thesis for this company.
Write ALL text in {output_lang}.

Respond ONLY with valid JSON (no markdown):
{{
  "agent": "{member.name}",
  "signal": "BUY|SELL|HOLD|STRONG_BUY|STRONG_SELL",
  "conviction": <float 0.0-1.0>,
  "thesis": "<2-4 sentence thesis in {output_lang}>",
  "key_metrics": ["<metric1>", "<metric2>"],
  "catalysts": ["<catalyst1>"],
  "risks": ["<risk1>"]
}}"""

    parsed = _invoke_llm(prompt)
    if not parsed:
        return PositionMemo(agent=member.name, signal="HOLD", conviction=0.5,
                            thesis=f"{member.name} analysis unavailable.")

    return PositionMemo(
        agent=str(parsed.get("agent", member.name)),
        signal=str(parsed.get("signal", "HOLD")).upper(),
        conviction=min(1.0, max(0.0, float(parsed.get("conviction", 0.5)))),
        thesis=str(parsed.get("thesis", "")),
        key_metrics=list(parsed.get("key_metrics", [])),
        catalysts=list(parsed.get("catalysts", [])),
        risks=list(parsed.get("risks", [])),
    )


def challenge(
    member: ICMember,
    own_memo: PositionMemo,
    target_memo: PositionMemo,
    ticker: str,
) -> Challenge:
    """Round 2: Agent challenges the target agent's position."""
    output_lang = get_output_language()
    prompt = f"""You are {member.name} ({member.framework}).
You are in an Investment Committee meeting for {ticker}.

YOUR POSITION:
Signal: {own_memo.signal} | Conviction: {own_memo.conviction:.0%}
Thesis: {own_memo.thesis}

TARGET — {target_memo.agent}'s POSITION:
Signal: {target_memo.signal} | Conviction: {target_memo.conviction:.0%}
Thesis: {target_memo.thesis}
Key Metrics: {', '.join(target_memo.key_metrics)}

TASK: Issue a focused, specific challenge to {target_memo.agent}'s position.
Identify the weakest point and attack it with data. Be constructive but rigorous.
Write ALL text in {output_lang}.

Respond ONLY with valid JSON:
{{
  "challenger": "{member.name}",
  "target": "{target_memo.agent}",
  "objection": "<specific, data-driven objection in {output_lang}>",
  "evidence": ["<supporting data point 1>"],
  "severity": "low|moderate|high"
}}"""

    parsed = _invoke_llm(prompt)
    if not parsed:
        return Challenge(
            challenger=member.name, target=target_memo.agent,
            objection=f"{member.name} could not formulate a challenge.",
            severity="low",
        )

    return Challenge(
        challenger=str(parsed.get("challenger", member.name)),
        target=str(parsed.get("target", target_memo.agent)),
        objection=str(parsed.get("objection", "")),
        evidence=list(parsed.get("evidence", [])),
        severity=str(parsed.get("severity", "moderate")).lower(),
    )


def rebut(
    member: ICMember,
    own_memo: PositionMemo,
    challenges_received: list[Challenge],
    ticker: str,
) -> Rebuttal:
    """Round 3: Agent defends their position against received challenges."""
    if not challenges_received:
        return Rebuttal(
            agent=member.name, challenger="None",
            defense="No challenges were directed at this agent.",
        )

    # Combine all challenges received
    challenge_text = "\n".join(
        f"— {c.challenger} ({c.severity}): {c.objection}"
        for c in challenges_received
    )
    output_lang = get_output_language()

    prompt = f"""You are {member.name} ({member.framework}).
Investment Committee meeting for {ticker}.

YOUR POSITION:
Signal: {own_memo.signal} | Conviction: {own_memo.conviction:.0%}
Thesis: {own_memo.thesis}

CHALLENGES RECEIVED:
{challenge_text}

TASK: Defend your position. If valid points are raised, make a concession.
Be honest — adjust your conviction if the challenge has merit.
Write ALL text in {output_lang}.

Respond ONLY with valid JSON:
{{
  "agent": "{member.name}",
  "challenger": "{challenges_received[0].challenger}",
  "defense": "<your rebuttal in {output_lang}>",
  "concession": "<any point you concede, or empty string>",
  "conviction_adjustment": <float -0.5 to +0.5, negative = challenge weakened your case>
}}"""

    parsed = _invoke_llm(prompt)
    if not parsed:
        return Rebuttal(
            agent=member.name, challenger=challenges_received[0].challenger,
            defense=f"{member.name} stands by their original thesis.",
        )

    return Rebuttal(
        agent=str(parsed.get("agent", member.name)),
        challenger=str(parsed.get("challenger", challenges_received[0].challenger)),
        defense=str(parsed.get("defense", "")),
        concession=str(parsed.get("concession", "")),
        conviction_adjustment=min(0.5, max(-0.5, float(parsed.get("conviction_adjustment", 0.0)))),
    )
