"""
src/engines/technical/war_room/agents.py
──────────────────────────────────────────────────────────────────────────────
6 Technical IC agents, each with a distinct theoretical framework.

Agents interpret the SAME computed engine data through different lenses:
  1. Trend Strategist    — Dow Theory + Trend Following
  2. Momentum Analyst    — Mean Reversion + Momentum Factor
  3. Volatility Analyst  — Options Pricing / Natenberg framework
  4. Volume/Flow Spec.   — Wyckoff Method
  5. Structure Analyst   — Market Profile + Price Action
  6. MTF Specialist      — Elder Triple Screen adaptation

Every agent MUST cite real computed data — no fabrication allowed.
"""

from __future__ import annotations

import logging
from typing import Any

from src.engines.technical.war_room.models import (
    TacticalMember,
    TacticalAssessment,
    TacticalConflict,
    TimeframeAssessment,
)
from src.utils.helpers import extract_json
from src.utils.language import get_output_language
from src.llm import get_llm, LLMTaskType

logger = logging.getLogger("365advisers.engines.technical.war_room.agents")

# ─── LLM Instance ───────────────────────────────────────────────────────────

_llm_agent = get_llm(LLMTaskType.FAST)


# ─── Agent Roster ────────────────────────────────────────────────────────────

WAR_ROOM_MEMBERS: list[TacticalMember] = [
    TacticalMember(
        name="Trend Strategist",
        role="Primary trend analyst",
        domain="trend",
        framework="Dow Theory + Trend Following (Covel)",
        bias_description="Seeks confirmed trends via SMA/EMA alignment and crossovers. Avoids trading chop. Believes 'the trend is your friend until it ends'.",
    ),
    TacticalMember(
        name="Momentum Analyst",
        role="Oscillator and momentum specialist",
        domain="momentum",
        framework="Mean-Reversion + Momentum Factor (Jegadeesh & Titman)",
        bias_description="Contrarian at RSI/Stochastic extremes, momentum-aligned in mid-zone. Cites empirical 3-12 month momentum persistence from Jegadeesh & Titman (1993).",
    ),
    TacticalMember(
        name="Volatility Analyst",
        role="Volatility regime and risk specialist",
        domain="volatility",
        framework="Options Pricing lens (Natenberg) + VIX framework",
        bias_description="Reads vol expansion as opportunity in ranging markets or risk in trends. Uses BB width and ATR relative to the asset's own calibrated norms.",
    ),
    TacticalMember(
        name="Volume/Flow Specialist",
        role="Volume and orderflow analyst",
        domain="volume",
        framework="Wyckoff Method (accumulation/distribution phases)",
        bias_description="Believes 'volume precedes price'. Identifies accumulation (smart money buying in ranges) vs distribution (smart money selling at tops). OBV divergence is the highest-conviction signal.",
    ),
    TacticalMember(
        name="Structure Analyst",
        role="Support/resistance and price structure specialist",
        domain="structure",
        framework="Market Profile (Dalton) + Price Action (Brooks)",
        bias_description="Thinks in levels, not signals. Evaluates risk/reward from distance to S/R. Strong levels with 3+ touches carry higher conviction. Patterns (double top/bottom) override oscillator signals.",
    ),
    TacticalMember(
        name="MTF Specialist",
        role="Multi-timeframe alignment analyst",
        domain="mtf",
        framework="Elder Triple Screen adaptation (6 TF: 15M → 1M)",
        bias_description="Distrusts any signal that exists on only one timeframe. Requires alignment across at least 3 of 6 TFs for high conviction. Cross-timeframe divergence is a warning.",
    ),
]


# ─── LLM Invocation Helper ──────────────────────────────────────────────────

def _invoke_llm(prompt: str, agent_name: str) -> dict:
    """Call LLM and parse JSON response. Returns {} on failure."""
    try:
        from src.observability import traced_llm_call
        result = traced_llm_call("gemini-2.5-flash", prompt, _llm_agent.invoke)
        raw = result.content if hasattr(result, "content") else str(result)
        logger.info(f"War Room [{agent_name}]: LLM returned {len(raw)} chars")
        logger.debug(f"War Room [{agent_name}]: raw response: {raw[:500]}")
        parsed = extract_json(raw)
        if parsed:
            return parsed
        logger.warning(f"War Room [{agent_name}]: could not parse LLM response. First 300 chars: {raw[:300]}")
        return {}
    except Exception as exc:
        logger.error(f"War Room [{agent_name}]: LLM call failed: {exc}", exc_info=True)
        return {}


# ─── Round 1: ASSESS ─────────────────────────────────────────────────────────

def assess(
    member: TacticalMember,
    ticker: str,
    engine_data: dict[str, Any],
) -> TacticalAssessment | None:
    """
    Generate the agent's initial assessment of their domain.

    The agent receives ONLY raw indicator values, asset statistics, and sector
    context.  No pre-computed scores or engine signals are shown — the agent
    must arrive at its own conclusion through its theoretical framework.

    Returns None if the LLM call fails (agent does not participate).
    """
    lang = get_output_language()

    # ── Extract raw data ─────────────────────────────────────────────────
    module_scores = engine_data.get("module_scores", [])
    own_module = next(
        (m for m in module_scores if m.get("name") == member.domain),
        {},
    )

    # Format OWN domain indicators (details only — no score, no signal)
    own_details = own_module.get("details", {})
    own_details_str = "\n".join(
        f"    {k}: {v}" for k, v in own_details.items()
    ) or "    (no data available)"

    # Format CROSS-REFERENCE data from other domains (details only)
    cross_ref_lines = []
    for m in module_scores:
        if m.get("name") == member.domain:
            continue
        details = m.get("details", {})
        if details:
            items = ", ".join(f"{k}={v}" for k, v in details.items())
            cross_ref_lines.append(f"  {m.get('name', '?')}: {items}")
    cross_ref_str = "\n".join(cross_ref_lines) or "  (no cross-reference data)"

    # Regime, asset context, sector
    regime = engine_data.get("regime", {})
    asset_ctx = engine_data.get("asset_context", {})
    sector_rel = engine_data.get("sector_relative", {})

    trend_reg = regime.get("trend_regime", "N/A")
    adx_val = regime.get("adx", "N/A")
    vol_reg = regime.get("volatility_regime", "N/A")
    opt_atr = asset_ctx.get("optimal_atr_pct", "N/A")
    avg_dr = asset_ctx.get("avg_daily_range_pct", "N/A")
    bb_med = asset_ctx.get("bb_width_median", "N/A")
    vol_pctl = asset_ctx.get("volatility_percentile", "N/A")
    sr_status = sector_rel.get("status", "N/A")
    sr_strength = sector_rel.get("relative_strength", "N/A")

    # JSON template
    json_template = (
        '{\n'
        '  "signal": "STRONG_BULLISH|BULLISH|NEUTRAL|BEARISH|STRONG_BEARISH",\n'
        '  "conviction": 0.0-1.0,\n'
        f'  "thesis": "<2-3 sentences interpreting the raw indicator data through your {member.framework} lens. CITE specific numbers.>",\n'
        '  "supporting_data": ["<indicator=value cited>", "<indicator=value cited>", "<indicator=value cited>"],\n'
        f'  "theoretical_framework": "<1 sentence: which principle of {member.framework} supports your reading>",\n'
        '  "cross_module_note": "<1 sentence observing another domain\'s raw data relevant to your assessment>"\n'
        '}'
    )

    prompt = f"""You are the **{member.name}** on an institutional Technical Analysis committee.

YOUR THEORETICAL FRAMEWORK: {member.framework}
YOUR ANALYTICAL BIAS: {member.bias_description}

You are analyzing **{ticker}**. You MUST cite specific numerical values from the raw indicator data below.
Do NOT invent data. Do NOT reference any score or pre-computed signal — interpret the raw numbers yourself.

RAW INDICATOR DATA FOR {ticker}:

  YOUR DOMAIN INDICATORS ({member.domain}):
{own_details_str}

  CROSS-REFERENCE DATA (other domains):
{cross_ref_str}

  REGIME DETECTION:
    Trend Regime: {trend_reg} (ADX={adx_val})
    Volatility Regime: {vol_reg}

  ASSET STATISTICS (self-calibrated for {ticker}):
    Historical ATR%: {opt_atr}%
    Avg Daily Range: {avg_dr}%
    BB Width Median: {bb_med}
    Volatility Percentile: {vol_pctl}

  SECTOR CONTEXT:
    Sector Status: {sr_status}
    Relative Strength vs Sector: {sr_strength}

TASK: Produce your domain assessment using your theoretical framework.
Interpret the raw data — what does each indicator tell you through the lens of {member.framework}?
Your conclusion (BULLISH / BEARISH / NEUTRAL) must be YOUR OWN, derived from the data and theory.

Respond ONLY with valid JSON. ALL text in {lang}.
{json_template}"""

    parsed = _invoke_llm(prompt, member.name)

    if not parsed:
        logger.warning(f"{member.name} LLM assessment failed for {ticker} — agent will not participate.")
        return None

    # ── Data-anchored conviction ceiling ─────────────────────────
    from .conviction_ceiling import compute_ceiling

    llm_conviction = min(1.0, max(0.0, float(parsed.get("conviction", 0.5))))
    ceiling = compute_ceiling(member.domain, own_details, asset_ctx)
    capped = min(llm_conviction, ceiling)

    if capped < llm_conviction:
        logger.info(
            f"TechIC [{member.name}] conviction capped: "
            f"LLM={llm_conviction:.0%} → ceiling={ceiling:.0%} → final={capped:.0%}"
        )

    return TacticalAssessment(
        agent=member.name,
        domain=member.domain,
        signal=str(parsed.get("signal", "NEUTRAL")).upper(),
        conviction=capped,
        thesis=str(parsed.get("thesis", "")),
        supporting_data=list(parsed.get("supporting_data", [])),
        theoretical_framework=str(parsed.get("theoretical_framework", "")),
        cross_module_note=str(parsed.get("cross_module_note", "")),
    )


# ─── Round 2: CONFLICT ──────────────────────────────────────────────────────

def challenge(
    member: TacticalMember,
    own_assessment: TacticalAssessment,
    target_assessment: TacticalAssessment,
    ticker: str,
) -> TacticalConflict | None:
    """
    Agent challenges the target whose assessment most conflicts with theirs.
    Returns None if LLM call fails.
    """
    lang = get_output_language()

    json_template = (
        '{\n'
        '  "disagreement": "<What specifically do you disagree with? 1-2 sentences>",\n'
        '  "challenger_evidence": ["<data point 1>", "<data point 2>"],\n'
        f'  "theoretical_basis": "<Which principle of {member.framework} supports your challenge?>",\n'
        '  "severity": "HIGH|MEDIUM|LOW"\n'
        '}'
    )

    prompt = f"""You are the **{member.name}** ({member.framework}).
You disagree with the **{target_assessment.agent}** about {ticker}.

YOUR ASSESSMENT:
  Signal: {own_assessment.signal}, Conviction: {own_assessment.conviction}
  Thesis: {own_assessment.thesis}

THEIR ASSESSMENT ({target_assessment.agent}):
  Signal: {target_assessment.signal}, Conviction: {target_assessment.conviction}
  Thesis: {target_assessment.thesis}
  Supporting Data: {target_assessment.supporting_data}

TASK: Challenge their position using your theoretical framework. Cite specific data that contradicts their thesis.

Respond ONLY with valid JSON. ALL text in {lang}.
{json_template}"""

    parsed = _invoke_llm(prompt, f"{member.name}_challenge")

    if not parsed:
        logger.warning(f"{member.name} challenge LLM failed — skipping conflict.")
        return None

    return TacticalConflict(
        challenger=member.name,
        target=target_assessment.agent,
        disagreement=str(parsed.get("disagreement", "")),
        challenger_evidence=list(parsed.get("challenger_evidence", [])),
        theoretical_basis=str(parsed.get("theoretical_basis", "")),
        severity=str(parsed.get("severity", "MEDIUM")).upper(),
    )


# ─── Round 3: TIMEFRAME RECONCILIATION ──────────────────────────────────────

def reconcile_timeframes(
    member: TacticalMember,
    own_assessment: TacticalAssessment,
    challenges_received: list[TacticalConflict],
    ticker: str,
    mtf_data: dict[str, Any] | None = None,
) -> TimeframeAssessment | None:
    """
    Agent reconciles their reading across timeframes and responds to challenges.
    Returns None if LLM call fails.
    """
    lang = get_output_language()

    # Build MTF context (raw data only — no scores)
    mtf_context = "No multi-timeframe data available."
    if mtf_data:
        tf_lines = []
        for tf_key, tf_info in mtf_data.items():
            trend = tf_info.get('trend', 'N/A')
            tf_lines.append(f"  {tf_key}: trend={trend}")
        mtf_context = "Multi-Timeframe Readings:\n" + "\n".join(tf_lines)

    # Build challenge context
    challenge_block = "No challenges received."
    if challenges_received:
        ch_lines = []
        for ch in challenges_received:
            ch_lines.append(
                f"  From {ch.challenger} ({ch.severity}): {ch.disagreement}\n"
                f"    Evidence: {ch.challenger_evidence}"
            )
        challenge_block = "Challenges received:\n" + "\n".join(ch_lines)

    json_template = (
        '{\n'
        '  "timeframe_alignment": "ALIGNED|DIVERGENT|PARTIAL",\n'
        '  "dominant_timeframe": "<e.g. 1D>",\n'
        '  "timeframe_readings": {"15M": "BULLISH|BEARISH|NEUTRAL", "1H": "...", "4H": "...", "1D": "...", "1W": "...", "1M": "..."},\n'
        '  "conviction_adjustment": -0.2 to +0.2,\n'
        '  "defense": "<1-2 sentences responding to challenges and explaining your timeframe reconciliation>"\n'
        '}'
    )

    prompt = f"""You are the **{member.name}** ({member.framework}).
You are reconciling your assessment of {ticker} across multiple timeframes and defending against challenges.

YOUR ORIGINAL ASSESSMENT:
  Signal: {own_assessment.signal}, Conviction: {own_assessment.conviction}
  Thesis: {own_assessment.thesis}

{mtf_context}

{challenge_block}

TASK:
1. Assess whether your signal holds across timeframes (ALIGNED / DIVERGENT / PARTIAL)
2. Identify which timeframe carries the most weight for your analysis
3. Respond to any challenges — defend, concede, or adjust
4. State your conviction adjustment (positive = more confident, negative = less)

Respond ONLY with valid JSON. ALL text in {lang}.
{json_template}"""

    parsed = _invoke_llm(prompt, f"{member.name}_timeframe")

    if not parsed:
        logger.warning(f"{member.name} timeframe LLM failed — skipping reconciliation.")
        return None

    return TimeframeAssessment(
        agent=member.name,
        timeframe_alignment=str(parsed.get("timeframe_alignment", "PARTIAL")).upper(),
        dominant_timeframe=str(parsed.get("dominant_timeframe", "1D")),
        timeframe_readings=dict(parsed.get("timeframe_readings", {})),
        conviction_adjustment=min(0.2, max(-0.2, float(parsed.get("conviction_adjustment", 0.0)))),
        defense=str(parsed.get("defense", "")),
    )
