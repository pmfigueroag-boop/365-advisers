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
from src.contracts.analysis import (
    TechnicalResult, ModuleScore, TechnicalBiasResult, PositionSizingResult,
)
from src.engines.technical.indicators import IndicatorEngine
from src.engines.technical.scoring import ScoringEngine as TechScoringModule
from src.engines.technical.purified_scoring import PurifiedScoringEngine
from src.engines.technical.formatter import build_technical_summary
from src.engines.technical.position_sizing import compute_position_sizing
from src.engines.technical.calibration import get_asset_context
from src.engines.technical.signal_logger import SignalLogger, SignalRecord
from src.engines.technical.regime_detector import (
    TrendRegimeDetector,
    VolatilityRegimeDetector,
    combine_regime_adjustments,
)

logger = logging.getLogger("365advisers.engines.technical")

# Module-level signal logger singleton
_signal_logger = SignalLogger()


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
          3. Run RegimeDetectors (trend + volatility regime)
          4. Run ScoringEngine (deterministic 0–10 scoring, regime-adjusted)
          5. Compute position sizing
          6. Package into TechnicalResult contract

        Args:
            features: Normalised TechnicalFeatureSet from the Feature Layer.

        Returns:
            TechnicalResult with score, signal, evidence, and per-module breakdown.
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

        # ── Step 2: Detect regimes ────────────────────────────────────────
        adx = getattr(features, "adx", None) or 20.0
        plus_di = getattr(features, "plus_di", None) or 20.0
        minus_di = getattr(features, "minus_di", None) or 20.0

        trend_regime = TrendRegimeDetector.detect(
            adx=adx, plus_di=plus_di, minus_di=minus_di,
        )
        vol_regime = VolatilityRegimeDetector.detect(
            ohlcv=features.ohlcv or [],
            current_bb_upper=features.bb_upper or 0.0,
            current_bb_lower=features.bb_lower or 0.0,
            current_atr=features.atr or 0.0,
        )
        regime_adjustments = combine_regime_adjustments(trend_regime, vol_regime)

        logger.info(
            f"TECH: Regimes for {features.ticker}: "
            f"trend={trend_regime.regime} (ADX={trend_regime.adx}), "
            f"vol={vol_regime.regime} (ratio={vol_regime.bb_width_ratio})"
        )

        # ── Step 3: Self-calibrate asset context ──────────────────────────
        asset_ctx = get_asset_context(
            ohlcv=features.ohlcv or [],
            ticker=features.ticker,
            price=features.current_price or 0.0,
        )

        logger.info(
            f"TECH: AssetContext for {features.ticker}: "
            f"optimal_atr={asset_ctx.optimal_atr_pct:.1f}%, "
            f"adr={asset_ctx.avg_daily_range_pct:.1f}%, "
            f"bars={asset_ctx.bars_available}"
        )

        # ── Step 4: Score indicators (regime-adjusted, calibrated) ─────────
        tech_score = TechScoringModule.compute(
            indicator_result,
            regime_adjustments=regime_adjustments,
            trend_regime=trend_regime.regime,
            price=features.current_price or 0.0,
            asset_ctx=asset_ctx,
        )

        # ── Step 4: Build full summary (backward compat) ──────────────────
        summary = build_technical_summary(
            ticker=features.ticker,
            tech_data=tech_data,
            result=indicator_result,
            score=tech_score,
            processing_start_ms=start_ms,
            trend_regime=trend_regime,
            vol_regime=vol_regime,
        )

        # ── Step 5: Map to TechnicalResult contract ───────────────────────
        module_scores = [
            ModuleScore(name="trend", score=tech_score.modules.trend,
                        signal=indicator_result.trend.status,
                        evidence=tech_score.evidence.trend,
                        details={"golden_cross": indicator_result.trend.golden_cross,
                                 "death_cross": indicator_result.trend.death_cross,
                                 "cross_age_bars": indicator_result.trend.cross_age_bars}),
            ModuleScore(name="momentum", score=tech_score.modules.momentum,
                        signal=indicator_result.momentum.status,
                        evidence=tech_score.evidence.momentum,
                        details={"rsi": indicator_result.momentum.rsi,
                                 "rsi_zone": indicator_result.momentum.rsi_zone,
                                 "divergence": indicator_result.momentum.divergence,
                                 "divergence_strength": indicator_result.momentum.divergence_strength}),
            ModuleScore(name="volatility", score=tech_score.modules.volatility,
                        signal=indicator_result.volatility.condition,
                        evidence=tech_score.evidence.volatility,
                        details={"atr_pct": indicator_result.volatility.atr_pct,
                                 "bb_position": indicator_result.volatility.bb_position}),
            ModuleScore(name="volume", score=tech_score.modules.volume,
                        signal=indicator_result.volume.status,
                        evidence=tech_score.evidence.volume,
                        details={"obv_trend": indicator_result.volume.obv_trend,
                                 "volume_vs_avg": indicator_result.volume.volume_vs_avg,
                                 "volume_price_confirmation": indicator_result.volume.volume_price_confirmation}),
            ModuleScore(name="structure", score=tech_score.modules.structure,
                        signal=indicator_result.structure.breakout_direction,
                        evidence=tech_score.evidence.structure,
                        details={"breakout_probability": indicator_result.structure.breakout_probability,
                                 "market_structure": indicator_result.structure.market_structure,
                                 "patterns": indicator_result.structure.patterns,
                                 "level_strength": indicator_result.structure.level_strength}),
        ]

        # Aggregate all evidence
        all_evidence = (
            tech_score.evidence.trend +
            tech_score.evidence.momentum +
            tech_score.evidence.volatility +
            tech_score.evidence.volume +
            tech_score.evidence.structure
        )

        # Build TechnicalBiasResult Pydantic model from dataclass
        bias_data = tech_score.bias
        bias_result = TechnicalBiasResult(
            primary_bias=bias_data.primary_bias,
            bias_strength=bias_data.bias_strength,
            trend_alignment=bias_data.trend_alignment,
            risk_reward_ratio=bias_data.risk_reward_ratio,
            key_levels=bias_data.key_levels,
            actionable_zone=bias_data.actionable_zone,
            time_horizon=bias_data.time_horizon,
            setup_quality=bias_data.setup_quality,
        )

        # ── Step 6: Compute position sizing ───────────────────────────────
        current_price = features.current_price or 0.0
        atr_val = features.atr or 0.0
        atr_pct_val = indicator_result.volatility.atr_pct
        pos_sizing = compute_position_sizing(
            price=current_price,
            atr=atr_val,
            atr_pct=atr_pct_val,
            signal=tech_score.signal,
            confidence=tech_score.confidence,
            risk_reward_ratio=bias_data.risk_reward_ratio,
            nearest_support=indicator_result.structure.nearest_support,
            nearest_resistance=indicator_result.structure.nearest_resistance,
        )
        pos_sizing_result = PositionSizingResult(
            method=pos_sizing.method,
            suggested_pct_of_portfolio=pos_sizing.suggested_pct_of_portfolio,
            stop_loss_price=pos_sizing.stop_loss_price,
            stop_loss_pct=pos_sizing.stop_loss_pct,
            take_profit_price=pos_sizing.take_profit_price,
            take_profit_pct=pos_sizing.take_profit_pct,
            risk_per_trade_pct=pos_sizing.risk_per_trade_pct,
            risk_reward_ratio=pos_sizing.risk_reward_ratio,
            position_conviction=pos_sizing.position_conviction,
            rationale=pos_sizing.rationale,
        )

        # ── Step 7: Log signal for backtesting ────────────────────────────
        try:
            _signal_logger.log(SignalRecord(
                ticker=features.ticker,
                timestamp=__import__('datetime').datetime.now(
                    __import__('datetime').timezone.utc
                ).isoformat(),
                signal=tech_score.signal,
                score=tech_score.aggregate,
                setup_quality=bias_data.setup_quality,
                confidence=tech_score.confidence,
                regime=trend_regime.regime,
                module_scores={
                    "trend": tech_score.modules.trend,
                    "momentum": tech_score.modules.momentum,
                    "volatility": tech_score.modules.volatility,
                    "volume": tech_score.modules.volume,
                    "structure": tech_score.modules.structure,
                },
                price_at_signal=current_price,
                bias=bias_data.primary_bias,
                position_sizing_pct=pos_sizing.suggested_pct_of_portfolio,
                stop_loss_price=pos_sizing.stop_loss_price,
                take_profit_price=pos_sizing.take_profit_price,
            ))
        except Exception as exc:
            logger.warning(f"TECH: Failed to log signal: {exc}")

        # ── Step 6b: Compute Purified Score (alpha-validated only) ──────
        try:
            purified = PurifiedScoringEngine.compute(indicator_result, features)
            purified_score_val = purified.aggregate
            purified_signal_val = purified.signal
            purified_evidence_val = purified.evidence
            logger.info(
                f"TECH: Purified score for {features.ticker}: "
                f"{purified.aggregate}/10 ({purified.signal}), "
                f"confidence={purified.confidence:.0%}"
            )
        except Exception as exc:
            logger.warning(f"TECH: Purified scoring failed: {exc}")
            purified_score_val = tech_score.aggregate
            purified_signal_val = tech_score.signal
            purified_evidence_val = []

        return TechnicalResult(
            ticker=features.ticker,
            technical_score=tech_score.aggregate,
            signal=tech_score.signal,
            strength=tech_score.strength,
            technical_confidence=tech_score.confidence,
            volatility_condition=indicator_result.volatility.condition,
            module_scores=module_scores,
            summary=summary,
            evidence=all_evidence,
            strongest_module=tech_score.strongest_module,
            weakest_module=tech_score.weakest_module,
            confirmation_level=tech_score.confirmation_level,
            bias=bias_result,
            position_sizing=pos_sizing_result,
            setup_quality=bias_data.setup_quality,
            purified_score=purified_score_val,
            purified_signal=purified_signal_val,
            purified_evidence=purified_evidence_val,
        )

