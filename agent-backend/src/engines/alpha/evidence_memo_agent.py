"""
src/engines/alpha/evidence_memo_agent.py
──────────────────────────────────────────────────────────────────────────────
Evidence Analyst Agent — LLM-powered interpretive memo for CASE Composite.

Interprets the CASE composite score, category subscores, convergence patterns,
and cross-category conflicts to produce an institutional-grade evidence memo.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from src.utils.helpers import extract_json
from src.config import get_settings
from src.llm import get_llm, LLMTaskType

logger = logging.getLogger("365advisers.engines.alpha.evidence_memo")
_settings = get_settings()

_llm = get_llm(LLMTaskType.FAST)


class EvidenceMemoOutput(TypedDict):
    signal: str
    conviction: str
    narrative: str
    key_data: list[str]
    risk_factors: list[str]


def synthesize_evidence_memo(
    ticker: str,
    composite_alpha: dict,
    category_summary: dict,
) -> EvidenceMemoOutput:
    """Generate an evidence memo interpreting the CASE composite score."""
    score = composite_alpha.get("score", 0)
    env = composite_alpha.get("environment", "N/A")
    active_cats = composite_alpha.get("active_categories", 0)
    convergence = composite_alpha.get("convergence_bonus", 0)
    conflicts = composite_alpha.get("cross_category_conflicts", [])
    subscores = composite_alpha.get("subscores", {})
    decay = composite_alpha.get("decay", {})

    sub_block = "\n".join(
        f"  - {cat}: score={data.get('score', 0):.0f}, "
        f"fired={data.get('fired', 0)}/{data.get('total', 0)}, "
        f"coverage={data.get('coverage', 0):.0f}%, "
        f"conflicts={'YES' if data.get('conflict_detected') else 'no'}"
        for cat, data in subscores.items()
    ) if subscores else "  No subscores available"

    fallback: EvidenceMemoOutput = {
        "signal": "BULLISH" if score >= 65 else "BEARISH" if score <= 35 else "NEUTRAL",
        "conviction": "HIGH" if score >= 75 else "MEDIUM" if score >= 45 else "LOW",
        "narrative": f"CASE Composite: {score:.0f}/100 ({env}). {active_cats} active categories.",
        "key_data": [f"CASE: {score:.0f}/100", f"Environment: {env}"],
        "risk_factors": ["LLM analysis not available — using deterministic fallback."],
    }

    prompt = f"""You are an institutional quantitative analyst evaluating the FACTORIAL EVIDENCE of a stock.
You are provided with CASE (Composite Alpha Score Engine) data for {ticker}.

CASE DATA FOR {ticker}:

[COMPOSITE]
- CASE Score: {score:.1f}/100
- Environment: {env}
- Active categories: {active_cats}/8
- Convergence Bonus: +{convergence:.1f}
- Cross-Category Conflicts: {conflicts if conflicts else 'None'}

[SUBSCORES BY CATEGORY]
{sub_block}

[DECAY/FRESHNESS]
- Applied: {decay.get('applied', 'N/A')}
- Freshness Level: {decay.get('freshness_level', 'N/A')}
- Average Freshness: {decay.get('average_freshness', 'N/A')}
- Expired Signals: {decay.get('expired_signals', 0)}

INSTRUCTIONS:
Respond ONLY with valid JSON (no markdown, no code blocks). ALL text in ENGLISH.
Interpret the CASE evidence: is there factorial convergence? Which categories are strongest/weakest?
Does the score justify a position? Are there conflicts that reduce confidence?

{{
  "signal": "BULLISH|BEARISH|NEUTRAL",
  "conviction": "HIGH|MEDIUM|LOW",
  "narrative": "<3-4 sentence synthesis interpreting the CASE score, category distribution, and whether the factorial evidence supports or contradicts the thesis. Cite specific scores.>",
  "key_data": ["<data 1>", "<data 2>", "<data 3>"],
  "risk_factors": ["<risk 1>", "<risk 2>"]
}}"""

    try:
        raw = _llm.invoke(prompt).content
        parsed = extract_json(raw)
        if not parsed:
            return fallback
        return {
            "signal": str(parsed.get("signal", fallback["signal"])).upper(),
            "conviction": str(parsed.get("conviction", fallback["conviction"])).upper(),
            "narrative": str(parsed.get("narrative", fallback["narrative"])),
            "key_data": list(parsed.get("key_data", fallback["key_data"])),
            "risk_factors": list(parsed.get("risk_factors", fallback["risk_factors"])),
        }
    except Exception as exc:
        logger.error(f"Evidence Memo Agent error for {ticker}: {exc}")
        return fallback
