"""
src/engines/technical/engine.py
──────────────────────────────────────────────────────────────────────────────
TechnicalEngine facade — entry point for the Technical Analysis layer.

Accepts a TechnicalFeatureSet (Layer 2 contract), runs the indicator and
scoring modules, and produces a TechnicalResult (Layer 3 contract).
"""

from __future__ import annotations

import time
import logging

from src.contracts.features import TechnicalFeatureSet
from src.contracts.analysis import TechnicalResult, ModuleScore
from src.engines.technical.indicators import IndicatorEngine
from src.engines.technical.scoring import ScoringEngine as TechScoringModule
from src.engines.technical.formatter import build_technical_summary

logger = logging.getLogger("365advisers.engines.technical")


class TechnicalEngine:
    """
    Façade for the Technical Analysis Engine (Layer 3b).

    Usage:
        features = extract_technical_features(price_history, market_metrics)
        result = TechnicalEngine.run(features)
    """

    @staticmethod
    def run(features: TechnicalFeatureSet) -> TechnicalResult:
        """
        Execute the full technical analysis pipeline:
          1. Build raw indicator dict from features
          2. Run IndicatorEngine (5 modules: trend, momentum, volatility, volume, structure)
          3. Run ScoringEngine (deterministic 0–10 scoring)
          4. Package into TechnicalResult contract

        Args:
            features: Normalised TechnicalFeatureSet from the Feature Layer.

        Returns:
            TechnicalResult with score, signal, and per-module breakdown.
        """
        start_ms = time.monotonic_ns() / 1e6

        # ── Rebuild indicator dict compatible with IndicatorEngine ─────────
        indicator_dict = {
            "sma50": features.sma_50,
            "sma200": features.sma_200,
            "ema20": features.ema_20,
            "rsi": features.rsi,
            "stoch_k": features.stoch_k,
            "stoch_d": features.stoch_d,
            "macd": features.macd,
            "macd_signal": features.macd_signal,
            "macd_hist": features.macd_hist,
            "bb_upper": features.bb_upper,
            "bb_lower": features.bb_lower,
            "bb_basis": features.bb_basis,
            "atr": features.atr,
            "volume": features.volume,
            "obv": features.obv,
        }

        tech_data = {
            "current_price": features.current_price,
            "indicators": indicator_dict,
            "ohlcv": features.ohlcv,
        }

        # ── Step 1: Compute indicators ────────────────────────────────────
        indicator_result = IndicatorEngine.compute(tech_data)

        # ── Step 2: Score indicators ──────────────────────────────────────
        tech_score = TechScoringModule.compute(indicator_result)

        # ── Step 3: Build full summary (backward compat) ──────────────────
        summary = build_technical_summary(
            ticker=features.ticker,
            tech_data=tech_data,
            result=indicator_result,
            score=tech_score,
            processing_start_ms=start_ms,
        )

        # ── Step 4: Map to TechnicalResult contract ───────────────────────
        module_scores = [
            ModuleScore(name="trend", score=tech_score.modules.trend,
                        signal=indicator_result.trend.status,
                        details={"golden_cross": indicator_result.trend.golden_cross,
                                 "death_cross": indicator_result.trend.death_cross}),
            ModuleScore(name="momentum", score=tech_score.modules.momentum,
                        signal=indicator_result.momentum.status,
                        details={"rsi": indicator_result.momentum.rsi,
                                 "rsi_zone": indicator_result.momentum.rsi_zone}),
            ModuleScore(name="volatility", score=tech_score.modules.volatility,
                        signal=indicator_result.volatility.condition,
                        details={"atr_pct": indicator_result.volatility.atr_pct,
                                 "bb_position": indicator_result.volatility.bb_position}),
            ModuleScore(name="volume", score=tech_score.modules.volume,
                        signal=indicator_result.volume.status,
                        details={"obv_trend": indicator_result.volume.obv_trend,
                                 "volume_vs_avg": indicator_result.volume.volume_vs_avg}),
            ModuleScore(name="structure", score=tech_score.modules.structure,
                        signal=indicator_result.structure.breakout_direction,
                        details={"breakout_probability": indicator_result.structure.breakout_probability}),
        ]

        return TechnicalResult(
            ticker=features.ticker,
            technical_score=tech_score.aggregate,
            signal=tech_score.signal,
            strength=tech_score.strength,
            volatility_condition=indicator_result.volatility.condition,
            module_scores=module_scores,
            summary=summary,
        )
