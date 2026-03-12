"""
src/engines/technical/analyst_agent.py
──────────────────────────────────────────────────────────────────────────────
Technical Analyst Agent — LLM-powered interpretive memo for Technical Analysis.

Single agent that produces 5 specialist opinions (Trend, Momentum, Volatility,
Volume, Structure) each with signal and conviction, plus a consensus thesis.
Uses real computed indicator data — every opinion must cite numeric evidence.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.helpers import extract_json
from src.config import get_settings

logger = logging.getLogger("365advisers.engines.technical.analyst")
_settings = get_settings()

_llm_analyst = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=_settings.GOOGLE_API_KEY,
)


class SpecialtyOpinion(TypedDict):
    signal: str          # BULLISH | BEARISH | NEUTRAL
    conviction: str      # HIGH | MEDIUM | LOW
    narrative: str       # 2-3 sentences citing real data
    key_data: list[str]  # 2-3 bullet points with key metrics


class TechnicalMemoOutput(TypedDict):
    trend: SpecialtyOpinion
    momentum: SpecialtyOpinion
    volatility: SpecialtyOpinion
    volume: SpecialtyOpinion
    structure: SpecialtyOpinion
    consensus: str            # 3-4 sentence executive synthesis
    consensus_signal: str     # BULLISH | BEARISH | NEUTRAL
    consensus_conviction: str # HIGH | MEDIUM | LOW
    tradingview_comparison: str  # Comparison with TradingView benchmark
    key_levels: str           # Support/Resistance with context
    timing: str               # Entry/exit timing recommendation
    risk_factors: list[str]   # 3+ technical risks


def synthesize_technical_memo(
    ticker: str,
    technical_summary: dict,
    regime: dict | None = None,
    mtf: dict | None = None,
) -> TechnicalMemoOutput:
    """
    Generate an institutional-grade technical analysis memo with 5 specialist
    opinions plus a consensus using actual computed indicator data.
    """
    summary = technical_summary.get("summary", {})
    indicators = technical_summary.get("indicators", {})
    price = technical_summary.get("current_price", 0)

    # ── Extract key data points ───────────────────────────────────────────
    trend = indicators.get("trend", {})
    momentum = indicators.get("momentum", {})
    volatility = indicators.get("volatility", {})
    volume = indicators.get("volume", {})
    structure = indicators.get("structure", {})
    subscores = summary.get("subscores", {})

    # Evidence from deterministic engine (V2)
    det_evidence = summary.get("evidence", {})
    confidence_level = summary.get("confirmation_level", "N/A")
    det_confidence = summary.get("technical_confidence", "N/A")
    strongest_mod = summary.get("strongest_module", "N/A")
    weakest_mod = summary.get("weakest_module", "N/A")

    # Build evidence block for prompt
    evidence_block = ""
    if isinstance(det_evidence, dict):
        for mod_name, ev_list in det_evidence.items():
            if ev_list:
                evidence_block += f"\n  {mod_name.upper()}: " + "; ".join(ev_list)

    # Regime info
    regime = regime or technical_summary.get("regime", {})
    trend_regime = regime.get("trend_regime", "N/A")
    vol_regime = regime.get("volatility_regime", "N/A")
    adx = regime.get("adx", "N/A")
    di_spread = regime.get("di_spread", "N/A")

    # MTF info
    mtf = mtf or technical_summary.get("mtf")
    mtf_block = ""
    if mtf and mtf.get("timeframe_scores"):
        tf_lines = []
        for tf in mtf["timeframe_scores"]:
            tf_lines.append(
                f"  - {tf['timeframe'].upper()}: Score {tf['score']}, "
                f"Signal {tf['signal']}, Trend {tf.get('trend', 'N/A')}"
            )
        mtf_block = f"""
[MULTI-TIMEFRAME ANALYSIS]
- MTF Aggregate Score: {mtf.get('mtf_aggregate', 'N/A')}/10
- MTF Signal: {mtf.get('mtf_signal', 'N/A')}
- Agreement Level: {mtf.get('agreement_level', 'N/A')} ({mtf.get('agreement_count', 0)}/4)
- Bonus Applied: {mtf.get('bonus_applied', 0)}
Timeframe Breakdown:
{chr(10).join(tf_lines)}"""

    # TradingView rating (benchmark)
    tv_rating = technical_summary.get("tradingview_rating", {})
    tv_overall_rec = tv_rating.get("recommendation", "N/A")
    tv_buy = tv_rating.get("buy", 0)
    tv_neutral = tv_rating.get("neutral", 0)
    tv_sell = tv_rating.get("sell", 0)
    tv_osc = tv_rating.get("oscillators", {})
    tv_ma = tv_rating.get("moving_averages", {})

    tv_block = f"""\n[TRADINGVIEW BENCHMARK (26 indicadores)]
- Overall: {tv_overall_rec} ({tv_buy} Buy, {tv_neutral} Neutral, {tv_sell} Sell)
- Oscillators: {tv_osc.get('recommendation', 'N/A')} ({tv_osc.get('buy', 0)}B / {tv_osc.get('neutral', 0)}N / {tv_osc.get('sell', 0)}S)
- Moving Averages: {tv_ma.get('recommendation', 'N/A')} ({tv_ma.get('buy', 0)}B / {tv_ma.get('neutral', 0)}N / {tv_ma.get('sell', 0)}S)""" if tv_overall_rec != "N/A" else ""

    # Patterns & structure
    patterns = structure.get("patterns", [])
    market_structure = structure.get("market_structure", "N/A")
    level_strength = structure.get("level_strength", {})
    strong_levels = [
        lvl for lvl, info in level_strength.items()
        if isinstance(info, dict) and info.get("strong")
    ]

    prompt = f"""Eres un analista técnico institucional de primer nivel.
Se te proporcionan datos técnicos REALES y CALCULADOS de {ticker}. Tu trabajo es emitir 5 opiniones especializadas (una por cada módulo del análisis técnico) y luego un CONSENSO que sintetice las 5 opiniones.

REGLA FUNDAMENTAL: Cada opinión DEBE citar datos numéricos específicos. No escribas generalidades. Cada afirmación requiere evidencia del análisis.

DATOS TÉCNICOS DE {ticker} (PRECIO ACTUAL: ${price}):

[SCORES Y SEÑALES]
- Technical Score: {summary.get('technical_score', 'N/A')}/10
- Signal: {summary.get('signal', 'N/A')}
- Signal Strength: {summary.get('signal_strength', 'N/A')}
- Subscores: Trend={subscores.get('trend', 'N/A')}, Momentum={subscores.get('momentum', 'N/A')}, Volatility={subscores.get('volatility', 'N/A')}, Volume={subscores.get('volume', 'N/A')}, Structure={subscores.get('structure', 'N/A')}

[TREND]
- Status: {summary.get('trend_status', 'N/A')}
- Price vs SMA50: {trend.get('price_vs_sma50', 'N/A')} (SMA50=${trend.get('sma_50', 'N/A')})
- Price vs SMA200: {trend.get('price_vs_sma200', 'N/A')} (SMA200=${trend.get('sma_200', 'N/A')})
- EMA20: ${trend.get('ema_20', 'N/A')}
- MACD: value={trend.get('macd', {}).get('value', 'N/A')}, signal={trend.get('macd', {}).get('signal', 'N/A')}, histogram={trend.get('macd', {}).get('histogram', 'N/A')}
- MACD Crossover: {trend.get('macd_crossover', 'N/A')}
- Golden Cross: {trend.get('golden_cross', False)} | Death Cross: {trend.get('death_cross', False)}

[MOMENTUM]
- Status: {summary.get('momentum_status', 'N/A')}
- RSI(14): {momentum.get('rsi', 'N/A')} (Zone: {momentum.get('rsi_zone', 'N/A')})
- Stochastic %K: {momentum.get('stochastic_k', 'N/A')} | %D: {momentum.get('stochastic_d', 'N/A')} (Zone: {momentum.get('stochastic_zone', 'N/A')})

[VOLATILITY]
- Condition: {summary.get('volatility_condition', 'N/A')}
- BB Position: {volatility.get('bb_position', 'N/A')}
- BB Upper: ${volatility.get('bb_upper', 'N/A')} | Lower: ${volatility.get('bb_lower', 'N/A')} | Width: {volatility.get('bb_width', 'N/A')}
- ATR: {volatility.get('atr', 'N/A')} ({(volatility.get('atr_pct', 0) * 100):.2f}% del precio)

[VOLUME]
- Strength: {summary.get('volume_strength', 'N/A')}
- Volume vs Avg20: {volume.get('volume_vs_avg_20', 'N/A')}x
- OBV Trend: {volume.get('obv_trend', 'N/A')}

[STRUCTURE]
- Breakout Direction: {summary.get('breakout_direction', 'N/A')}
- Breakout Probability: {summary.get('breakout_probability', 'N/A')}
- Nearest Resistance: ${structure.get('nearest_resistance', 'N/A')} ({structure.get('distance_to_resistance_pct', 'N/A')}%)
- Nearest Support: ${structure.get('nearest_support', 'N/A')} ({structure.get('distance_to_support_pct', 'N/A')}%)
- Market Structure: {market_structure}
- Patterns Detected: {', '.join(patterns) if patterns else 'None'}
- Strong Levels: {', '.join(f'${s}' for s in strong_levels) if strong_levels else 'None'}

[REGIME DETECTION]
- Trend Regime: {trend_regime} (ADX={adx}, DI Spread={di_spread})
- Volatility Regime: {vol_regime} (BB Width Ratio={regime.get('bb_width_ratio', 'N/A')}, ATR Trend={regime.get('atr_trend', 'N/A')})
{mtf_block}
{tv_block}

[DETERMINISTIC ENGINE EVIDENCE]
- Confidence: {det_confidence} (Level: {confidence_level})
- Strongest Module: {strongest_mod}
- Weakest Module: {weakest_mod}
- Evidence Trail:{evidence_block if evidence_block else ' None available'}

INSTRUCCIONES DE OUTPUT:
Responde SOLO con JSON válido (sin markdown, sin code blocks). TODO en ESPAÑOL.
Cada especialidad emite: signal (BULLISH/BEARISH/NEUTRAL), conviction (HIGH/MEDIUM/LOW), narrative (2-3 oraciones con datos), key_data (2-3 datos clave citados).
El consensus sintetiza las 5 opiniones en una tesis unificada.

REGLA CRÍTICA DE CONSISTENCIA:
El motor determinista ha producido la señal: {summary.get('signal', 'N/A')} con score {summary.get('technical_score', 'N/A')}/10.
Tu consensus_signal NO PUEDE contradecir esta señal determinista:
- Si el motor dice STRONG_BUY o BUY, tu consensus_signal DEBE ser BULLISH.
- Si el motor dice STRONG_SELL o SELL, tu consensus_signal DEBE ser BEARISH.
- Si el motor dice NEUTRAL, puedes emitir BULLISH, BEARISH o NEUTRAL según la evidencia.
Si no estás de acuerdo con el motor, explica en el consensus POR QUÉ hay matices, pero MANTÉN la dirección del motor.
tradingview_comparison: Compara tu veredicto con TradingView. Si concuerdan, menciona la validación cruzada. Si difieren, explica QUÉ ve nuestro motor (régimen, MTF, structure V2) que TradingView no captura.

{{
  "trend": {{
    "signal": "BULLISH|BEARISH|NEUTRAL",
    "conviction": "HIGH|MEDIUM|LOW",
    "narrative": "<Opinión del especialista de Tendencia citando SMA50, SMA200, MACD, cruces. 2-3 oraciones.>",
    "key_data": ["<dato clave 1>", "<dato clave 2>"]
  }},
  "momentum": {{
    "signal": "BULLISH|BEARISH|NEUTRAL",
    "conviction": "HIGH|MEDIUM|LOW",
    "narrative": "<Opinión del especialista de Momentum citando RSI, Stochastic, zonas. 2-3 oraciones.>",
    "key_data": ["<dato clave 1>", "<dato clave 2>"]
  }},
  "volatility": {{
    "signal": "BULLISH|BEARISH|NEUTRAL",
    "conviction": "HIGH|MEDIUM|LOW",
    "narrative": "<Opinión del especialista de Volatilidad citando BB, ATR%, régimen. 2-3 oraciones.>",
    "key_data": ["<dato clave 1>", "<dato clave 2>"]
  }},
  "volume": {{
    "signal": "BULLISH|BEARISH|NEUTRAL",
    "conviction": "HIGH|MEDIUM|LOW",
    "narrative": "<Opinión del especialista de Volumen citando Vol/Avg, OBV trend. 2-3 oraciones.>",
    "key_data": ["<dato clave 1>", "<dato clave 2>"]
  }},
  "structure": {{
    "signal": "BULLISH|BEARISH|NEUTRAL",
    "conviction": "HIGH|MEDIUM|LOW",
    "narrative": "<Opinión del especialista de Estructura citando S/R, breakout prob, patrones. 2-3 oraciones.>",
    "key_data": ["<dato clave 1>", "<dato clave 2>"]
  }},
  "consensus": "<Síntesis ejecutiva de 3-4 oraciones que reconcilie las 5 opiniones. Debe indicar si hay unanimidad o divergencia entre especialistas, y la conclusión técnica principal con datos.>",
  "consensus_signal": "BULLISH|BEARISH|NEUTRAL",
  "consensus_conviction": "HIGH|MEDIUM|LOW",
  "tradingview_comparison": "<Comparación con TradingView: si concuerdan menciónalo como validación; si difieren, explica qué detecta nuestro motor (régimen, MTF, structure V2, patterns) que TV no captura. 2-3 oraciones.>",
  "key_levels": "<Niveles clave: soporte más cercano, resistencia más cercana, niveles fuertes con contexto.>",
  "timing": "<Recomendación de timing: cuándo entrar, stop-loss basado en soporte, target basado en resistencia.>",
  "risk_factors": ["<riesgo técnico 1 con dato>", "<riesgo técnico 2 con dato>", "<riesgo técnico 3>"]
}}"""

    def _parse_opinion(raw: dict, name: str) -> SpecialtyOpinion:
        return {
            "signal": str(raw.get("signal", "NEUTRAL")).upper(),
            "conviction": str(raw.get("conviction", "LOW")).upper(),
            "narrative": str(raw.get("narrative", f"Análisis de {name} no disponible.")),
            "key_data": list(raw.get("key_data", [])),
        }

    def _fallback_opinion(name: str, score: float, status: str) -> SpecialtyOpinion:
        return {
            "signal": "BULLISH" if score >= 6 else "BEARISH" if score < 4 else "NEUTRAL",
            "conviction": "LOW",
            "narrative": f"{name}: Score {score}/10, status {status}. Memo detallado no disponible.",
            "key_data": [f"Score: {score}/10", f"Status: {status}"],
        }

    fallback: TechnicalMemoOutput = {
        "trend": _fallback_opinion("Trend", subscores.get("trend", 0), summary.get("trend_status", "N/A")),
        "momentum": _fallback_opinion("Momentum", subscores.get("momentum", 0), summary.get("momentum_status", "N/A")),
        "volatility": _fallback_opinion("Volatility", subscores.get("volatility", 0), summary.get("volatility_condition", "N/A")),
        "volume": _fallback_opinion("Volume", subscores.get("volume", 0), summary.get("volume_strength", "N/A")),
        "structure": _fallback_opinion("Structure", subscores.get("structure", 0), summary.get("breakout_direction", "N/A")),
        "consensus": f"Análisis técnico de {ticker}: Score {summary.get('technical_score', 'N/A')}/10, señal {summary.get('signal', 'N/A')}.",
        "consensus_signal": summary.get("signal", "NEUTRAL").replace("STRONG_BUY", "BULLISH").replace("BUY", "BULLISH").replace("STRONG_SELL", "BEARISH").replace("SELL", "BEARISH"),
        "consensus_conviction": "LOW",
        "tradingview_comparison": f"TradingView: {tv_overall_rec} ({tv_buy}B/{tv_neutral}N/{tv_sell}S)." if tv_overall_rec != "N/A" else "Datos de TradingView no disponibles.",
        "key_levels": f"Resistencia: ${structure.get('nearest_resistance', 'N/A')}, Soporte: ${structure.get('nearest_support', 'N/A')}.",
        "timing": "Análisis de timing no disponible.",
        "risk_factors": ["Análisis de riesgos técnicos no disponible."],
    }

    def _validate_signal_consistency(
        llm_signal: str,
        engine_signal: str,
    ) -> str:
        """
        Guardrail: ensure LLM consensus does not contradict the deterministic engine.
        Returns the corrected signal.
        """
        engine_upper = engine_signal.upper()
        llm_upper = llm_signal.upper()

        engine_bullish = engine_upper in ("STRONG_BUY", "BUY")
        engine_bearish = engine_upper in ("STRONG_SELL", "SELL")

        if engine_bullish and llm_upper == "BEARISH":
            logger.warning(
                f"GUARDRAIL: LLM said BEARISH but engine says {engine_upper} for {ticker}. Correcting to BULLISH."
            )
            return "BULLISH"
        if engine_bearish and llm_upper == "BULLISH":
            logger.warning(
                f"GUARDRAIL: LLM said BULLISH but engine says {engine_upper} for {ticker}. Correcting to BEARISH."
            )
            return "BEARISH"

        return llm_upper

    try:
        raw_response = _llm_analyst.invoke(prompt).content
        parsed = extract_json(raw_response)

        if not parsed:
            logger.warning(f"Technical Analyst: Could not parse LLM response for {ticker}")
            return fallback

        engine_signal = summary.get("signal", "NEUTRAL")
        raw_consensus_signal = str(parsed.get("consensus_signal", fallback["consensus_signal"])).upper()
        validated_signal = _validate_signal_consistency(raw_consensus_signal, engine_signal)

        return {
            "trend": _parse_opinion(parsed.get("trend", {}), "Trend"),
            "momentum": _parse_opinion(parsed.get("momentum", {}), "Momentum"),
            "volatility": _parse_opinion(parsed.get("volatility", {}), "Volatility"),
            "volume": _parse_opinion(parsed.get("volume", {}), "Volume"),
            "structure": _parse_opinion(parsed.get("structure", {}), "Structure"),
            "consensus": str(parsed.get("consensus", fallback["consensus"])),
            "consensus_signal": validated_signal,
            "consensus_conviction": str(parsed.get("consensus_conviction", fallback["consensus_conviction"])).upper(),
            "tradingview_comparison": str(parsed.get("tradingview_comparison", fallback["tradingview_comparison"])),
            "key_levels": str(parsed.get("key_levels", fallback["key_levels"])),
            "timing": str(parsed.get("timing", fallback["timing"])),
            "risk_factors": list(parsed.get("risk_factors", fallback["risk_factors"])),
        }
    except Exception as exc:
        logger.error(f"Technical Analyst Agent error for {ticker}: {exc}")
        return fallback
