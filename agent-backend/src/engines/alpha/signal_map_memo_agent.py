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

from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.helpers import extract_json
from src.config import get_settings

logger = logging.getLogger("365advisers.engines.alpha.signal_map_memo")
_settings = get_settings()

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=_settings.GOOGLE_API_KEY,
)


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
        "narrative": f"{ticker}: {len(fired)}/{total} señales activas ({fired_pct:.0f}%).",
        "key_data": [f"Activas: {len(fired)}/{total}", f"Categorías: {len(cats_with_fired)}"],
        "risk_factors": ["Análisis LLM no disponible — usando fallback determinístico."],
    }

    prompt = f"""Eres un analista cuantitativo institucional que interpreta el MAPA DE SEÑALES de una acción.
Se te proporcionan datos REALES de las señales individuales de {ticker}.

MAPA DE SEÑALES DE {ticker}:

[RESUMEN]
- Total señales: {total}
- Señales activas: {len(fired)} ({fired_pct:.0f}%)
- Categorías con señales activas: {len(cats_with_fired)}/8

[SEÑALES ACTIVAS (Top 12)]
{signal_table}

[DISTRIBUCIÓN POR CATEGORÍA]
{cat_table}

[SEÑALES INACTIVAS]
- {total - len(fired)} señales no disparadas

INSTRUCCIONES:
Responde SOLO con JSON válido (sin markdown, sin code blocks). TODO en ESPAÑOL.
Analiza el patrón del mapa de señales: ¿hay convergencia entre categorías? ¿Las señales
fuertes dominan o son principalmente weak? ¿Qué categorías están ausentes y qué implica?

{{
  "signal": "BULLISH|BEARISH|NEUTRAL",
  "conviction": "HIGH|MEDIUM|LOW",
  "narrative": "<3-4 oraciones analizando el patrón de convergencia/divergencia de señales, distribución de fuerza, y cobertura factorial. Cita señales y datos específicos.>",
  "key_data": ["<dato 1>", "<dato 2>", "<dato 3>"],
  "risk_factors": ["<riesgo 1>", "<riesgo 2>"]
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
