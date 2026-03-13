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

from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.helpers import extract_json
from src.config import get_settings

logger = logging.getLogger("365advisers.engines.alpha.memo_agent")
_settings = get_settings()

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=_settings.GOOGLE_API_KEY,
)


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
        "narrative": f"{ticker}: {fired}/{total} señales Alpha activas. "
                     f"Fuerza compuesta: {composite.get('overall_strength', 0) * 100:.0f}%.",
        "key_data": [f"Señales activas: {fired}/{total}",
                     f"Fuerza: {composite.get('overall_strength', 0) * 100:.0f}%"],
        "risk_factors": ["Análisis LLM no disponible — usando fallback determinístico."],
    }

    prompt = f"""Eres un analista cuantitativo institucional especializado en señales Alpha.
Se te proporcionan datos REALES y CALCULADOS del perfil de señales de {ticker}.

DATOS DE SEÑALES ALPHA DE {ticker}:

[RESUMEN]
- Señales activas: {fired} de {total}
- Fuerza compuesta: {composite.get('overall_strength', 0) * 100:.1f}%
- Confianza: {composite.get('overall_confidence', 'N/A')}
- Categoría dominante: {composite.get('dominant_category', 'N/A')}
- Categorías activas: {composite.get('active_categories', 0)}
- Bonus multi-categoría: {composite.get('multi_category_bonus', False)}

[CASE COMPOSITE]
- Score: {case_score}/100
- Environment: {composite_alpha.get('environment', 'N/A')}
- Convergence Bonus: {composite_alpha.get('convergence_bonus', 0)}
- Conflicts: {composite_alpha.get('cross_category_conflicts', [])}

[SEÑALES ACTIVAS (Top 8)]
{signal_block}

[CATEGORÍAS CON SEÑALES]
{cat_block}

[DECAY/FRESHNESS]
- Applied: {decay.get('applied', 'N/A')}
- Freshness Level: {decay.get('freshness_level', 'N/A')}
- Average Freshness: {decay.get('average_freshness', 'N/A')}

INSTRUCCIONES:
Responde SOLO con JSON válido (sin markdown, sin code blocks). TODO en ESPAÑOL.
Analiza el perfil de señales Alpha y emite una opinión fundamentada.

{{
  "signal": "BULLISH|BEARISH|NEUTRAL",
  "conviction": "HIGH|MEDIUM|LOW",
  "narrative": "<Síntesis ejecutiva de 3-4 oraciones que interprete el patrón de señales: qué categorías dominan, si hay convergencia o divergencia, y qué implica para la tesis de inversión. Cita datos específicos.>",
  "key_data": ["<dato clave 1>", "<dato clave 2>", "<dato clave 3>"],
  "risk_factors": ["<riesgo 1 con datos>", "<riesgo 2>"]
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
