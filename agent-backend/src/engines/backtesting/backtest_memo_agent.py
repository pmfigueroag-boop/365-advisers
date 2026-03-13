"""
src/engines/backtesting/backtest_memo_agent.py
──────────────────────────────────────────────────────────────────────────────
Backtest Analyst Agent — LLM-powered interpretive memo for Backtest Evidence.

Interprets backtest results (win rate, avg return, sharpe, profit factor)
to produce an institutional-grade memo evaluating statistical edge.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.helpers import extract_json
from src.config import get_settings

logger = logging.getLogger("365advisers.engines.backtesting.memo_agent")
_settings = get_settings()

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=_settings.GOOGLE_API_KEY,
)


class BacktestMemoOutput(TypedDict):
    signal: str
    conviction: str
    narrative: str
    key_data: list[str]
    risk_factors: list[str]


def synthesize_backtest_memo(
    ticker: str,
    backtest_results: list[dict],
) -> BacktestMemoOutput:
    """Generate a backtest evidence memo analyzing statistical edge."""

    def n(v) -> float:
        return float(v) if isinstance(v, (int, float)) and not (isinstance(v, float) and v != v) else 0.0

    if not backtest_results:
        return {
            "signal": "NEUTRAL",
            "conviction": "LOW",
            "narrative": f"No hay resultados de backtest disponibles para {ticker}.",
            "key_data": [],
            "risk_factors": ["Sin datos de backtest — no es posible evaluar edge estadístico."],
        }

    count = len(backtest_results)
    total_signals = sum(n(r.get("total_signals", 0)) for r in backtest_results)
    avg_wr = sum(n(r.get("win_rate", 0)) for r in backtest_results) / count
    avg_ret = sum(n(r.get("avg_return", 0)) for r in backtest_results) / count
    avg_sharpe = sum(n(r.get("sharpe_ratio", 0)) for r in backtest_results) / count
    avg_pf = sum(n(r.get("profit_factor", 0)) for r in backtest_results) / count

    # Build per-signal results
    results_block = "\n".join(
        f"  - {r.get('signal_id', 'N/A')}: WR={n(r.get('win_rate', 0)):.1f}%, "
        f"Return={n(r.get('avg_return', 0)):.2f}%, "
        f"Sharpe={n(r.get('sharpe_ratio', 0)):.2f}, "
        f"PF={n(r.get('profit_factor', 0)):.2f}, "
        f"Signals={n(r.get('total_signals', 0)):.0f}"
        for r in backtest_results[:10]
    )

    fallback: BacktestMemoOutput = {
        "signal": "BULLISH" if avg_wr >= 60 and avg_ret > 0 else
                  "BEARISH" if avg_wr < 40 or avg_ret < -1 else "NEUTRAL",
        "conviction": "HIGH" if total_signals >= 10 and avg_wr >= 65 else
                      "MEDIUM" if total_signals >= 5 else "LOW",
        "narrative": f"Backtest de {count} estrategias. WR: {avg_wr:.1f}%, "
                     f"Ret: {avg_ret:.2f}%, Sharpe: {avg_sharpe:.2f}.",
        "key_data": [f"Win Rate: {avg_wr:.1f}%", f"Avg Return: {avg_ret:.2f}%"],
        "risk_factors": ["Análisis LLM no disponible — usando fallback determinístico."],
    }

    prompt = f"""Eres un analista cuantitativo institucional que evalúa la EVIDENCIA DE BACKTEST.
Se te proporcionan resultados REALES de backtesting de señales Alpha para {ticker}.

RESULTADOS DE BACKTEST DE {ticker}:

[AGREGADOS]
- Estrategias evaluadas: {count}
- Total observaciones: {total_signals:.0f}
- Win Rate promedio: {avg_wr:.1f}%
- Retorno promedio: {avg_ret:+.2f}%
- Sharpe promedio: {avg_sharpe:.2f}
- Profit Factor promedio: {avg_pf:.2f}

[RESULTADOS POR SEÑAL]
{results_block}

INSTRUCCIONES:
Responde SOLO con JSON válido (sin markdown, sin code blocks). TODO en ESPAÑOL.
Evalúa si las señales tienen edge estadístico real. ¿El win rate y el retorno son
significativos? ¿El sharpe justifica riesgo? ¿Hay suficientes observaciones?

{{
  "signal": "BULLISH|BEARISH|NEUTRAL",
  "conviction": "HIGH|MEDIUM|LOW",
  "narrative": "<3-4 oraciones evaluando el edge estadístico: ¿las señales predicen correctamente? ¿El retorno justifica el riesgo? ¿Hay suficiente muestra? Cita métricas específicas.>",
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
        logger.error(f"Backtest Memo Agent error for {ticker}: {exc}")
        return fallback
