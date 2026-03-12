"""
src/engines/technical/formatter.py
─────────────────────────────────────────────────────────────────────────────
OutputFormatter — assembles IndicatorResult + TechnicalScore into the final
TechnicalSummary dict that the API endpoint returns.

No LLM. Pure structured output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import asdict

from src.engines.technical.indicators import IndicatorResult
from src.engines.technical.scoring import TechnicalScore
from src.utils.helpers import sanitize_data


def build_technical_summary(
    ticker: str,
    tech_data: dict,
    result: IndicatorResult,
    score: TechnicalScore,
    active_indicators: list[str] | None = None,
    processing_start_ms: float | None = None,
    trend_regime=None,
    vol_regime=None,
) -> dict:
    """
    Builds the complete TechnicalSummary dict matching the schema defined in
    the architecture plan.

    Args:
        ticker:             Stock symbol
        tech_data:          Raw output from fetch_technical_data()
        result:             IndicatorResult from IndicatorEngine.compute()
        score:              TechnicalScore from ScoringEngine.compute()
        active_indicators:  List of indicator names that are active / used
        processing_start_ms: time.monotonic_ns() / 1e6 at start, for latency

    Returns:
        Sanitized dict ready to be JSON-serialised by FastAPI.
    """
    import time

    processing_ms = (
        round(time.monotonic_ns() / 1e6 - processing_start_ms)
        if processing_start_ms is not None
        else None
    )

    trend = result.trend
    mom   = result.momentum
    vol   = result.volatility
    vol_r = result.volume
    struct = result.structure

    # ── Indicator state block ──────────────────────────────────────────────────
    indicators: dict = {
        "trend": {
            "sma_50":           trend.sma_50,
            "sma_200":          trend.sma_200,
            "ema_20":           trend.ema_20,
            "macd": {
                "value":    trend.macd_value,
                "signal":   trend.macd_signal,
                "histogram":trend.macd_histogram,
            },
            "price_vs_sma50":   trend.price_vs_sma50,
            "price_vs_sma200":  trend.price_vs_sma200,
            "macd_crossover":   trend.macd_crossover,
            "golden_cross":     trend.golden_cross,
            "death_cross":      trend.death_cross,
        },
        "momentum": {
            "rsi":              mom.rsi,
            "rsi_zone":         mom.rsi_zone,
            "stochastic_k":     mom.stoch_k,
            "stochastic_d":     mom.stoch_d,
            "stochastic_zone":  mom.stoch_zone,
        },
        "volatility": {
            "bb_upper":         vol.bb_upper,
            "bb_lower":         vol.bb_lower,
            "bb_basis":         vol.bb_basis,
            "bb_width":         vol.bb_width,
            "bb_position":      vol.bb_position,
            "atr":              vol.atr,
            "atr_pct":          vol.atr_pct,
        },
        "volume": {
            "obv":              vol_r.obv,
            "obv_trend":        vol_r.obv_trend,
            "current_volume":   vol_r.current_volume,
            "volume_vs_avg_20": vol_r.volume_vs_avg,
        },
        "structure": {
            "resistance_levels":             struct.resistance_levels,
            "support_levels":                struct.support_levels,
            "nearest_resistance":            struct.nearest_resistance,
            "nearest_support":               struct.nearest_support,
            "distance_to_resistance_pct":    struct.distance_to_resistance_pct,
            "distance_to_support_pct":       struct.distance_to_support_pct,
            "breakout_probability":          struct.breakout_probability,
            "breakout_direction":            struct.breakout_direction,
            "market_structure":              struct.market_structure,
            "level_strength":                struct.level_strength,
            "patterns":                      struct.patterns,
        },
    }

    # ── Summary block ─────────────────────────────────────────────────────────
    summary: dict = {
        "trend_status":        trend.status,
        "momentum_status":     mom.status,
        "volatility_condition":vol.condition,
        "volume_strength":     vol_r.status,
        "breakout_probability":f"{int(struct.breakout_probability * 100)}%",
        "breakout_direction":  struct.breakout_direction,
        "signal":              score.signal,
        "signal_strength":     score.strength,
        "technical_score":     score.aggregate,
        "subscores": {
            "trend":      score.modules.trend,
            "momentum":   score.modules.momentum,
            "volatility": score.modules.volatility,
            "volume":     score.modules.volume,
            "structure":  score.modules.structure,
        },
        "technical_confidence": score.confidence,
        "strongest_module":     score.strongest_module,
        "weakest_module":       score.weakest_module,
        "confirmation_level":   score.confirmation_level,
        "evidence": {
            "trend":      score.evidence.trend,
            "momentum":   score.evidence.momentum,
            "volatility": score.evidence.volatility,
            "volume":     score.evidence.volume,
            "structure":  score.evidence.structure,
        },
        "bias": {
            "primary_bias":      score.bias.primary_bias,
            "bias_strength":     score.bias.bias_strength,
            "trend_alignment":   score.bias.trend_alignment,
            "risk_reward_ratio": score.bias.risk_reward_ratio,
            "key_levels":        score.bias.key_levels,
            "actionable_zone":   score.bias.actionable_zone,
            "time_horizon":      score.bias.time_horizon,
        },
    }

    # ── TradingView Rating (reference benchmark) ────────────────────────────
    tv_sum = tech_data.get("tv_summary", {})
    tv_osc = tech_data.get("tv_oscillators", {})
    tv_mas = tech_data.get("tv_moving_averages", {})

    tradingview_rating: dict = {
        "recommendation": tv_sum.get("RECOMMENDATION", "UNKNOWN"),
        "buy":     tv_sum.get("BUY", 0),
        "sell":    tv_sum.get("SELL", 0),
        "neutral": tv_sum.get("NEUTRAL", 0),
        "oscillators": {
            "recommendation": (tv_osc.get("RECOMMENDATION", "UNKNOWN")
                               if isinstance(tv_osc, dict) else "UNKNOWN"),
            "buy":     tv_osc.get("BUY", 0) if isinstance(tv_osc, dict) else 0,
            "sell":    tv_osc.get("SELL", 0) if isinstance(tv_osc, dict) else 0,
            "neutral": tv_osc.get("NEUTRAL", 0) if isinstance(tv_osc, dict) else 0,
        },
        "moving_averages": {
            "recommendation": (tv_mas.get("RECOMMENDATION", "UNKNOWN")
                               if isinstance(tv_mas, dict) else "UNKNOWN"),
            "buy":     tv_mas.get("BUY", 0) if isinstance(tv_mas, dict) else 0,
            "sell":    tv_mas.get("SELL", 0) if isinstance(tv_mas, dict) else 0,
            "neutral": tv_mas.get("NEUTRAL", 0) if isinstance(tv_mas, dict) else 0,
        },
    }
    # ── Regime data (V2) ───────────────────────────────────────────────────
    from src.engines.technical.regime_detector import combine_regime_adjustments
    regime_block: dict = {}
    if trend_regime and vol_regime:
        regime_block = {
            "trend_regime": trend_regime.regime,
            "volatility_regime": vol_regime.regime,
            "adx": trend_regime.adx,
            "di_spread": trend_regime.di_spread,
            "plus_di": trend_regime.plus_di,
            "minus_di": trend_regime.minus_di,
            "bb_width_ratio": vol_regime.bb_width_ratio,
            "atr_trend": vol_regime.atr_trend,
            "weight_adjustments": combine_regime_adjustments(trend_regime, vol_regime),
        }

    return sanitize_data({
        "ticker":           ticker.upper(),
        "analysis_type":    "technical",
        "timestamp":        datetime.now(tz=timezone.utc).isoformat(),
        "interval":         "1D",
        "current_price":    tech_data.get("current_price"),
        "data_source":      "yfinance + tradingview-ta",
        "exchange":         tech_data.get("exchange", ""),
        "indicators":       indicators,
        "summary":          summary,
        "regime":           regime_block,
        "tv_recommendation":tech_data.get("indicators", {}).get("tv_recommendation", "UNKNOWN"),
        "tradingview_rating": tradingview_rating,
        "active_indicators": active_indicators or [
            "SMA50", "SMA200", "EMA20", "MACD",
            "RSI", "Stochastic",
            "BollingerBands", "ATR",
            "OBV", "VolumeProfile",
            "Support/Resistance", "BreakoutDetector",
        ],
        "processing_time_ms": processing_ms,
    })
