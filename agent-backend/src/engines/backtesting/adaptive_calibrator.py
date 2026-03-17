"""
src/engines/backtesting/adaptive_calibrator.py
--------------------------------------------------------------------------
Adaptive Signal Calibrator -- closes the learning loop.

Reads backtest results, computes dynamic weights/thresholds per signal,
and produces regime-conditional weight tables. The Governor then validates
all proposed changes before they are applied.

Hardened version with:
  1. Bayesian shrinkage weight formula (IC-weighted)
  2. Low-sample penalization factor
  3. Regime-specific minimum weight thresholds
  4. Out-of-sample temporal stability validation
  5. Percentage change diff reporting
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict

from src.engines.alpha_signals.models import AlphaSignalDefinition
from src.engines.alpha_signals.registry import registry as signal_registry
from src.engines.backtesting.calibration_models import (
    CalibrationConfig,
    CalibrationResult,
    CalibrationVersion,
    CalibratedSignalConfig,
    ParameterChange,
    ParameterType,
    RegimeWeightTable,
)
from src.engines.backtesting.models import (
    BacktestReport,
    SignalPerformanceRecord,
)
from src.engines.backtesting.regime_detector import MarketRegime, RegimeDetector

logger = logging.getLogger("365advisers.calibrator")


# ─── Constants ───────────────────────────────────────────────────────────────

# Regime-specific minimum weights: even the worst signal in that regime
# must not drop below this floor. Prevents over-suppression.
REGIME_MIN_WEIGHTS: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.BULL: {
        "momentum": 0.6, "growth": 0.5, "value": 0.3,
        "quality": 0.4, "flow": 0.3, "volatility": 0.3,
        "event": 0.3, "macro": 0.3,
    },
    MarketRegime.BEAR: {
        "momentum": 0.3, "growth": 0.3, "value": 0.6,
        "quality": 0.6, "flow": 0.3, "volatility": 0.5,
        "event": 0.4, "macro": 0.4,
    },
    MarketRegime.RANGE_BOUND: {
        "momentum": 0.3, "growth": 0.3, "value": 0.5,
        "quality": 0.4, "flow": 0.4, "volatility": 0.3,
        "event": 0.3, "macro": 0.3,
    },
    MarketRegime.HIGH_VOL: {
        "momentum": 0.3, "growth": 0.3, "value": 0.3,
        "quality": 0.3, "flow": 0.3, "volatility": 0.5,
        "event": 0.5, "macro": 0.4,
    },
    MarketRegime.LOW_VOL: {
        "momentum": 0.5, "growth": 0.4, "value": 0.4,
        "quality": 0.5, "flow": 0.3, "volatility": 0.3,
        "event": 0.3, "macro": 0.3,
    },
}

# Regime category boost multipliers
REGIME_CATEGORY_BOOST: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.BULL: {"momentum": 1.3, "growth": 1.2, "value": 0.8},
    MarketRegime.BEAR: {"value": 1.4, "quality": 1.3, "momentum": 0.7},
    MarketRegime.RANGE_BOUND: {"value": 1.2, "flow": 1.1, "momentum": 0.8},
    MarketRegime.HIGH_VOL: {"volatility": 1.3, "event": 1.2, "momentum": 0.6},
    MarketRegime.LOW_VOL: {"momentum": 1.2, "quality": 1.1, "volatility": 0.7},
}


class AdaptiveCalibrator:
    """
    Core calibration engine. Reads backtest results and produces
    calibrated signal configs.

    Weight Update Formula (Bayesian Shrinkage):
    -------------------------------------------
    w_new = base_weight × [ alpha × IC_score + (1 - alpha) × prior ]

    Where:
      - IC_score = rank_IC × sign(excess_return)     -- information coefficient
      - alpha = n / (n + kappa)                       -- Bayesian shrinkage factor
      - kappa = min_observations (default 50)         -- shrinkage constant
      - prior = 1.0                                   -- prior weight (no change)
      - Result clamped to [weight_clamp_min, weight_clamp_max]
      - Low-sample penalty: alpha → alpha × penalty   where penalty < 1 for n < kappa

    This means:
      - With 10 observations: alpha ≈ 0.17, mostly prior (conservative)
      - With 50 observations: alpha = 0.50, equal blend
      - With 200 observations: alpha ≈ 0.80, mostly data-driven
    """

    def __init__(self, config: CalibrationConfig | None = None) -> None:
        self.config = config or CalibrationConfig()

    def calibrate(
        self,
        report: BacktestReport,
        regime_map: dict | None = None,
        current_regime: MarketRegime | None = None,
    ) -> tuple[list[ParameterChange], list[CalibratedSignalConfig], list[RegimeWeightTable]]:
        """
        Analyze backtest results and produce calibration changes.

        Returns
        -------
        tuple
            (proposed_changes, calibrated_configs, regime_weight_tables)
        """
        t0 = time.monotonic()
        proposed_changes: list[ParameterChange] = []
        calibrated_configs: list[CalibratedSignalConfig] = []

        for record in report.signal_results:
            signal_def = signal_registry.get(record.signal_id)
            if signal_def is None:
                continue

            config = self._calibrate_signal(record, signal_def)
            calibrated_configs.append(config)

            # Detect changes
            changes = self._detect_changes(record, signal_def, config)
            proposed_changes.extend(changes)

        # Regime-conditional weights
        regime_tables = []
        if regime_map and report.signal_results:
            regime_tables = self._compute_regime_weights(report, regime_map)

        elapsed = time.monotonic() - t0
        logger.info(
            f"CALIBRATOR: Produced {len(proposed_changes)} changes, "
            f"{len(calibrated_configs)} configs, "
            f"{len(regime_tables)} regime tables in {elapsed:.2f}s"
        )

        return proposed_changes, calibrated_configs, regime_tables

    # ── Core Weight Formula ──────────────────────────────────────────────

    def _calibrate_signal(
        self,
        record: SignalPerformanceRecord,
        signal_def: AlphaSignalDefinition,
    ) -> CalibratedSignalConfig:
        """Compute calibrated config for a single signal using Bayesian shrinkage."""
        base_weight = signal_def.weight
        n = record.total_firings
        kappa = self.config.min_observations  # shrinkage constant

        # --- (1) Bayesian shrinkage factor ---
        # alpha = n / (n + kappa), ranges from 0 (no data) to ~1 (lots of data)
        alpha = n / (n + kappa) if (n + kappa) > 0 else 0.0

        # --- (2) Low-sample penalization ---
        # Additional penalty for very small samples: penalty = sqrt(n / kappa)
        # At n=50 (kappa), penalty=1.0 (no penalty).
        # At n=10, penalty=0.45. At n=25, penalty=0.71.
        sample_penalty = min(math.sqrt(n / kappa) if kappa > 0 else 1.0, 1.0)
        alpha *= sample_penalty

        # --- (3) Information Coefficient (IC) score ---
        # Combines Sharpe (risk-adjusted) + hit_rate (directional accuracy)
        sharpe_20 = record.sharpe_ratio.get(20, 0.0)
        hr_20 = record.hit_rate.get(20, 0.5)

        # IC = sharpe_component × hr_component
        # sharpe_component: tanh(sharpe/2) maps [-inf,inf] → [-1,1]
        sharpe_component = math.tanh(sharpe_20 / 2.0)

        # hr_component: (hr - 0.5) × 2 maps [0,1] → [-1,1], centered at 0.5
        hr_component = (hr_20 - 0.5) * 2.0

        # Blend: 60% sharpe, 40% hit rate
        ic_score = 0.6 * sharpe_component + 0.4 * hr_component

        # --- (4) Weight update: Bayesian blend ---
        # w_new = base × [alpha × (1 + ic_score) + (1 - alpha) × 1.0]
        # ic_score ∈ [-1, 1], so (1 + ic_score) ∈ [0, 2]
        # prior = 1.0 (no change)
        data_driven = 1.0 + ic_score  # [0, 2]
        prior = 1.0
        scale = alpha * data_driven + (1.0 - alpha) * prior

        new_weight = base_weight * scale
        new_weight = max(
            self.config.weight_clamp_min,
            min(new_weight, self.config.weight_clamp_max),
        )

        # --- (5) Out-of-sample stability check ---
        stability = self._compute_temporal_stability(record)

        # Dynamic confidence score
        confidence = self._compute_dynamic_confidence(record, stability)

        # Half-life from empirical decay
        half_life = record.empirical_half_life

        return CalibratedSignalConfig(
            signal_id=record.signal_id,
            weight=round(new_weight, 4),
            threshold=signal_def.threshold,
            strong_threshold=signal_def.strong_threshold,
            half_life=half_life,
            confidence_score=round(confidence, 4),
            enabled=signal_def.enabled,
        )

    # ── Temporal Stability (Out-of-Sample Proxy) ─────────────────────────

    def _compute_temporal_stability(
        self, record: SignalPerformanceRecord
    ) -> float:
        """
        Estimate out-of-sample stability from in-sample metrics.

        Uses the ratio of Sharpe across different forward windows as a
        proxy for temporal persistence. If a signal has high Sharpe at
        T+5 but negative Sharpe at T+20, it's unstable.

        Returns
        -------
        float
            Stability score in [0, 1]. 1.0 = perfectly consistent across windows.
        """
        sharpes = record.sharpe_ratio
        if len(sharpes) < 2:
            return 0.5  # Insufficient data for stability assessment

        vals = list(sharpes.values())
        n = len(vals)

        # Sign consistency: what fraction of windows agree on direction?
        positive = sum(1 for v in vals if v > 0)
        sign_consistency = max(positive, n - positive) / n

        # Magnitude consistency: CV of absolute Sharpe ratios
        # Low CV = consistent magnitude, high CV = erratic
        abs_vals = [abs(v) for v in vals]
        mean_abs = sum(abs_vals) / n if n > 0 else 0.0
        if mean_abs > 0.01:
            variance = sum((v - mean_abs) ** 2 for v in abs_vals) / n
            cv = math.sqrt(variance) / mean_abs
            magnitude_consistency = 1.0 / (1.0 + cv)  # Inverse CV → [0, 1]
        else:
            magnitude_consistency = 0.5

        # Decay consistency: is the Sharpe degrading smoothly?
        # Check if Sharpe at longer windows is not dramatically worse
        sorted_windows = sorted(sharpes.keys())
        if len(sorted_windows) >= 3:
            short_sharpe = sharpes.get(sorted_windows[0], 0.0)
            long_sharpe = sharpes.get(sorted_windows[-1], 0.0)
            if abs(short_sharpe) > 0.01:
                decay_ratio = long_sharpe / short_sharpe
                # decay_ratio near 1 = stable; near 0 = decaying; negative = reversing
                decay_score = max(0.0, min(decay_ratio, 1.0))
            else:
                decay_score = 0.5
        else:
            decay_score = 0.5

        # Weighted blend
        stability = (
            0.4 * sign_consistency
            + 0.3 * magnitude_consistency
            + 0.3 * decay_score
        )

        return max(0.0, min(stability, 1.0))

    # ── Dynamic Confidence ───────────────────────────────────────────────

    def _compute_dynamic_confidence(
        self, record: SignalPerformanceRecord, stability: float = 0.5,
    ) -> float:
        """
        Confidence = f(hit_rate, sample_size, stability, sharpe).

        Combines multiple quality dimensions into 0-1 score.
        Now includes temporal stability as a direct input.
        """
        hr = record.hit_rate.get(20, 0.5)
        n = record.total_firings
        sharpe = record.sharpe_ratio.get(20, 0.0)

        # Hit rate component: sigmoid centered at 0.55
        hr_score = 1.0 / (1.0 + math.exp(-10 * (hr - 0.55)))

        # Sample size component: sqrt scaling, saturates ~200
        n_score = min(math.sqrt(n) / math.sqrt(200), 1.0)

        # Sharpe component: sigmoid centered at 0
        sharp_score = 1.0 / (1.0 + math.exp(-2 * sharpe))

        # Weighted average (now with temporal stability)
        confidence = (
            0.30 * hr_score
            + 0.20 * n_score
            + 0.25 * sharp_score
            + 0.25 * stability
        )

        return max(0.0, min(confidence, 1.0))

    # ── Change Detection ─────────────────────────────────────────────────

    def _detect_changes(
        self,
        record: SignalPerformanceRecord,
        signal_def: AlphaSignalDefinition,
        config: CalibratedSignalConfig,
    ) -> list[ParameterChange]:
        """Detect parameter differences between current and calibrated config."""
        changes: list[ParameterChange] = []

        # Weight change
        old_w = signal_def.weight
        new_w = config.weight
        if old_w > 0:
            change_pct = abs(new_w - old_w) / old_w
            if change_pct > 0.01:  # >1% change
                sharpe_20 = record.sharpe_ratio.get(20, 0.0)
                hr_20 = record.hit_rate.get(20, 0.0)
                stability = self._compute_temporal_stability(record)
                n = record.total_firings
                kappa = self.config.min_observations

                # Compute shrinkage factor for reporting
                alpha = n / (n + kappa) if (n + kappa) > 0 else 0.0
                penalty = min(math.sqrt(n / kappa) if kappa > 0 else 1.0, 1.0)

                changes.append(ParameterChange(
                    signal_id=record.signal_id,
                    parameter=ParameterType.WEIGHT,
                    old_value=round(old_w, 4),
                    new_value=round(new_w, 4),
                    change_pct=round(change_pct, 4),
                    evidence=(
                        f"Sharpe={sharpe_20:+.2f} HR={hr_20:.0%} "
                        f"n={n} alpha={alpha * penalty:.2f} "
                        f"stability={stability:.2f}"
                    ),
                    # Structured metrics for Governor
                    stability=round(stability, 4),
                    hit_rate=round(hr_20, 4),
                    sample_size=n,
                    sharpe=round(sharpe_20, 4),
                ))

        # Half-life change
        if config.half_life is not None:
            from src.engines.alpha_decay.models import DEFAULT_HALF_LIFE_DAYS
            configured_hl = DEFAULT_HALF_LIFE_DAYS.get(
                record.category.value, 30.0
            )
            if configured_hl > 0:
                hl_change = abs(config.half_life - configured_hl) / configured_hl
                if hl_change > 0.20:
                    changes.append(ParameterChange(
                        signal_id=record.signal_id,
                        parameter=ParameterType.HALF_LIFE,
                        old_value=configured_hl,
                        new_value=round(config.half_life, 1),
                        change_pct=round(hl_change, 4),
                        evidence=(
                            f"Empirical={config.half_life:.1f}d vs "
                            f"configured={configured_hl:.1f}d"
                        ),
                        sample_size=record.total_firings,
                    ))

        return changes

    # ── Regime-Conditional Weights ───────────────────────────────────────

    def _compute_regime_weights(
        self,
        report: BacktestReport,
        regime_map: dict,
    ) -> list[RegimeWeightTable]:
        """
        Compute per-signal weights conditioned on market regime.

        Applies regime category boosts AND regime-specific minimum thresholds.
        """
        regime_tables: list[RegimeWeightTable] = []

        for regime in MarketRegime:
            boosts = REGIME_CATEGORY_BOOST.get(regime, {})
            min_weights = REGIME_MIN_WEIGHTS.get(regime, {})
            weights: dict[str, float] = {}
            sharpes: dict[str, float] = {}

            for record in report.signal_results:
                base_weight = 1.0
                sig_def = signal_registry.get(record.signal_id)
                if sig_def:
                    base_weight = sig_def.weight

                cat = record.category.value
                boost = boosts.get(cat, 1.0)
                cat_min = min_weights.get(cat, 0.3)

                # Apply regime boost to the Bayesian-calibrated weight
                n = record.total_firings
                kappa = self.config.min_observations
                alpha = n / (n + kappa) if (n + kappa) > 0 else 0.0
                penalty = min(math.sqrt(n / kappa) if kappa > 0 else 1.0, 1.0)
                alpha *= penalty

                sharpe_20 = record.sharpe_ratio.get(20, 0.0)
                ic_score = math.tanh(sharpe_20 / 2.0)
                data_driven = 1.0 + ic_score
                prior = 1.0
                scale = alpha * data_driven + (1.0 - alpha) * prior

                regime_weight = base_weight * scale * boost

                # Enforce regime-specific minimum
                regime_weight = max(cat_min, min(regime_weight, 3.0))

                weights[record.signal_id] = round(regime_weight, 4)
                sharpes[record.signal_id] = round(sharpe_20, 4)

            # Count regime days
            regime_days = sum(1 for r in regime_map.values() if r == regime)

            regime_tables.append(RegimeWeightTable(
                regime=regime.value,
                weights=weights,
                sample_size=regime_days,
                sharpe_by_signal=sharpes,
            ))

        return regime_tables
