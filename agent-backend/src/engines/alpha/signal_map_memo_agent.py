"""
src/engines/alpha/signal_map_memo_agent.py
──────────────────────────────────────────────────────────────────────────────
Signal Map Analyst Agent — LLM-powered interpretive memo for Signal Map.

Analyzes the pattern of fired vs inactive signals, convergence across
categories, and strength distribution to produce an institutional-grade memo.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from src.utils.helpers import extract_json
from src.config import get_settings
from src.llm import get_llm, LLMTaskType

logger = logging.getLogger("365advisers.engines.alpha.signal_map_memo")
_settings = get_settings()

_llm = get_llm(LLMTaskType.FAST)


class SignalMapMemoOutput(TypedDict):
    signal: str
    conviction: str
    narrative: str
    key_data: list[str]
    risk_factors: list[str]


def synthesize_signal_map_memo(
    ticker: str,
    signals: list[dict],
    category_summary: dict,
) -> SignalMapMemoOutput:
    """Generate a signal map memo analyzing fired/inactive signal patterns."""
    fired = [s for s in signals if s.get("fired")]
    total = len(signals)
    fired_pct = (len(fired) / total * 100) if total > 0 else 0

    # Group by category
    cats_with_fired = {
        cat: data for cat, data in category_summary.items()
        if data.get("fired", 0) > 0
    }

    # Build signal table
    signal_table = "\n".join(
        f"  - {s.get('signal_name', 'N/A')} [{s.get('category', 'N/A')}]: "
        f"strength={s.get('strength', 'N/A')}, "
        f"value={s.get('value', 'N/A')}, "
        f"threshold={s.get('threshold', 'N/A')}"
        for s in fired[:12]
    ) if fired else "  No signals fired"

    cat_table = "\n".join(
        f"  - {cat}: {data.get('fired', 0)}/{data.get('total', 0)} fired, "
        f"strength={data.get('composite_strength', 0):.2f}, "
        f"dominant={data.get('dominant_strength', 'N/A')}"
        for cat, data in cats_with_fired.items()
    ) if cats_with_fired else "  No active categories"

    fallback: SignalMapMemoOutput = {
        "signal": "BULLISH" if fired_pct >= 55 else "BEARISH" if fired_pct <= 25 else "NEUTRAL",
        "conviction": "HIGH" if fired_pct >= 70 else "MEDIUM" if fired_pct >= 40 else "LOW",
        "narrative": f"{ticker}: {len(fired)}/{total} signals active ({fired_pct:.0f}%).",
        "key_data": [f"Active: {len(fired)}/{total}", f"Categories: {len(cats_with_fired)}"],
        "risk_factors": ["LLM analysis not available — using deterministic fallback."],
    }

    prompt = f"""You are an institutional quantitative analyst interpreting the SIGNAL MAP of a stock.
You are provided with REAL signal data for {ticker}.

SIGNAL MAP FOR {ticker}:

[SUMMARY]
- Total signals: {total}
- Active signals: {len(fired)} ({fired_pct:.0f}%)
- Categories with active signals: {len(cats_with_fired)}/8

[ACTIVE SIGNALS (Top 12)]
{signal_table}

[DISTRIBUTION BY CATEGORY]
{cat_table}

[INACTIVE SIGNALS]
- {total - len(fired)} signals not fired

INSTRUCTIONS:
Respond ONLY with valid JSON (no markdown, no code blocks). ALL text in ENGLISH.
Analyze the signal map pattern: is there convergence across categories? Do strong signals
dominate or are they mostly weak? Which categories are absent and what does it imply?

{{
  "signal": "BULLISH|BEARISH|NEUTRAL",
  "conviction": "HIGH|MEDIUM|LOW",
  "narrative": "<3-4 sentences analyzing the convergence/divergence pattern of signals, strength distribution, and factorial coverage. Cite specific signals and data.>",
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
        logger.error(f"Signal Map Memo Agent error for {ticker}: {exc}")
        return fallback
