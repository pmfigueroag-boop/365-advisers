"""
src/engines/alpha/alpha_memo_agent.py
──────────────────────────────────────────────────────────────────────────────
Alpha Signals Analyst Agent — LLM-powered interpretive memo for Alpha Signals.

Produces a structured memo with signal, conviction, narrative, key_data,
and risk_factors based on the computed signal profile data.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from src.utils.helpers import extract_json
from src.config import get_settings
from src.llm import get_llm, LLMTaskType

logger = logging.getLogger("365advisers.engines.alpha.memo_agent")
_settings = get_settings()

_llm = get_llm(LLMTaskType.FAST)


class AlphaMemoOutput(TypedDict):
    signal: str           # BULLISH | BEARISH | NEUTRAL
    conviction: str       # HIGH | MEDIUM | LOW
    narrative: str        # 3-4 sentence executive synthesis
    key_data: list[str]   # 3-5 key data points
    risk_factors: list[str]  # 2-3 risk factors


def synthesize_alpha_memo(
    ticker: str,
    signal_profile: dict,
) -> AlphaMemoOutput:
    """
    Generate an institutional-grade alpha signals memo using the
    evaluated signal profile data.
    """
    fired = signal_profile.get("fired_signals", 0)
    total = signal_profile.get("total_signals", 0)
    composite = signal_profile.get("composite", {})
    category_summary = signal_profile.get("category_summary", {})
    composite_alpha = signal_profile.get("composite_alpha", {})
    signals = signal_profile.get("signals", [])

    # Build signal list for prompt
    fired_signals = [s for s in signals if s.get("fired")]
    top_fired = sorted(
        fired_signals,
        key=lambda s: {"strong": 3, "moderate": 2, "weak": 1}.get(s.get("strength", "weak"), 0),
        reverse=True,
    )[:8]

    signal_block = "\n".join(
        f"  - {s.get('signal_name', 'N/A')} [{s.get('category', 'N/A')}]: "
        f"strength={s.get('strength', 'N/A')}, value={s.get('value', 'N/A')}"
        for s in top_fired
    ) if top_fired else "  No signals fired"

    cat_block = "\n".join(
        f"  - {cat}: {data.get('fired', 0)}/{data.get('total', 0)} fired, "
        f"strength={data.get('composite_strength', 0):.2f}, "
        f"confidence={data.get('confidence', 'N/A')}"
        for cat, data in category_summary.items()
        if data.get("fired", 0) > 0
    ) if category_summary else "  No category data"

    case_score = composite_alpha.get("score", "N/A")
    decay = composite_alpha.get("decay", {})

    fallback: AlphaMemoOutput = {
        "signal": "BULLISH" if composite.get("overall_strength", 0) >= 0.65 else
                  "BEARISH" if composite.get("overall_strength", 0) <= 0.3 else "NEUTRAL",
        "conviction": "HIGH" if composite.get("overall_strength", 0) >= 0.75 else
                      "MEDIUM" if composite.get("overall_strength", 0) >= 0.45 else "LOW",
        "narrative": f"{ticker}: {fired}/{total} Alpha signals active. "
                     f"Composite strength: {composite.get('overall_strength', 0) * 100:.0f}%.",
        "key_data": [f"Active signals: {fired}/{total}",
                     f"Strength: {composite.get('overall_strength', 0) * 100:.0f}%"],
        "risk_factors": ["LLM analysis not available — using deterministic fallback."],
    }

    prompt = f"""You are an institutional quantitative analyst specialized in Alpha signals.
You are provided with REAL, COMPUTED signal profile data for {ticker}.

ALPHA SIGNAL DATA FOR {ticker}:

[SUMMARY]
- Active signals: {fired} of {total}
- Composite strength: {composite.get('overall_strength', 0) * 100:.1f}%
- Confidence: {composite.get('overall_confidence', 'N/A')}
- Dominant category: {composite.get('dominant_category', 'N/A')}
- Active categories: {composite.get('active_categories', 0)}
- Multi-category bonus: {composite.get('multi_category_bonus', False)}

[CASE COMPOSITE]
- Score: {case_score}/100
- Environment: {composite_alpha.get('environment', 'N/A')}
- Convergence Bonus: {composite_alpha.get('convergence_bonus', 0)}
- Conflicts: {composite_alpha.get('cross_category_conflicts', [])}

[ACTIVE SIGNALS (Top 8)]
{signal_block}

[CATEGORIES WITH SIGNALS]
{cat_block}

[DECAY/FRESHNESS]
- Applied: {decay.get('applied', 'N/A')}
- Freshness Level: {decay.get('freshness_level', 'N/A')}
- Average Freshness: {decay.get('average_freshness', 'N/A')}

INSTRUCTIONS:
Respond ONLY with valid JSON (no markdown, no code blocks). ALL text in ENGLISH.
Analyze the Alpha signal profile and provide a well-founded opinion.

{{
  "signal": "BULLISH|BEARISH|NEUTRAL",
  "conviction": "HIGH|MEDIUM|LOW",
  "narrative": "<Executive synthesis of 3-4 sentences interpreting the signal pattern: which categories dominate, whether there is convergence or divergence, and what it implies for the investment thesis. Cite specific data.>",
  "key_data": ["<key data 1>", "<key data 2>", "<key data 3>"],
  "risk_factors": ["<risk 1 with data>", "<risk 2>"]
}}"""

    try:
        raw = _llm.invoke(prompt).content
        parsed = extract_json(raw)

        if not parsed:
            logger.warning(f"Alpha Memo Agent: Could not parse LLM response for {ticker}")
            return fallback

        return {
            "signal": str(parsed.get("signal", fallback["signal"])).upper(),
            "conviction": str(parsed.get("conviction", fallback["conviction"])).upper(),
            "narrative": str(parsed.get("narrative", fallback["narrative"])),
            "key_data": list(parsed.get("key_data", fallback["key_data"])),
            "risk_factors": list(parsed.get("risk_factors", fallback["risk_factors"])),
        }
    except Exception as exc:
        logger.error(f"Alpha Memo Agent error for {ticker}: {exc}")
        return fallback
