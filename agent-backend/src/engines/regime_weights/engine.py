"""
src/engines/regime_weights/engine.py
──────────────────────────────────────────────────────────────────────────────
Adaptive Weight Engine — orchestrator.

Pipeline:
  1. Detect current market regime via RegimeDetector
  2. Evaluate historical signal performance per regime
  3. Compute regime multipliers per signal (Sharpe-based normalisation)
  4. Multiply base DynamicWeight × regime multiplier
  5. Output effective weights for CASE
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

import pandas as pd

from src.engines.backtesting.models import SignalEvent
from src.engines.backtesting.regime_detector import MarketRegime, RegimeDetector
from src.engines.regime_weights.evaluator import RegimePerformanceEvaluator
from src.engines.regime_weights.models import (
    AdaptiveWeightConfig,
    AdaptiveWeightReport,
    RegimeSignalStats,
    RegimeWeightProfile,
)

logger = logging.getLogger("365advisers.regime_weights.engine")


class AdaptiveWeightEngine:
    """
    Computes regime-adaptive signal weights.

    Usage::

        engine = AdaptiveWeightEngine()
        report = engine.compute_adaptive_weights(ohlcv, events_by_signal)
        weights = engine.get_effective_weights(report)
    """

    def __init__(self, config: AdaptiveWeightConfig | None = None) -> None:
        self.config = config or AdaptiveWeightConfig()
        self._detector = RegimeDetector()
        self._evaluator = RegimePerformanceEvaluator()

    # ── Public API ────────────────────────────────────────────────────────

    def compute_adaptive_weights(
        self,
        benchmark_ohlcv: pd.DataFrame,
        events_by_signal: dict[str, list[SignalEvent]],
        config: AdaptiveWeightConfig | None = None,
    ) -> AdaptiveWeightReport:
        """
        Run full regime-adaptive weight computation.

        Parameters
        ----------
        benchmark_ohlcv : pd.DataFrame
            OHLCV data for the benchmark (e.g. SPY).
        events_by_signal : dict
            {signal_id: [SignalEvent, ...]}
        config : AdaptiveWeightConfig | None
            Override configuration.

        Returns
        -------
        AdaptiveWeightReport
        """
        cfg = config or self.config

        # 1. Classify regimes
        regimes = self._detector.classify(benchmark_ohlcv)
        if not regimes:
            logger.warning("REGIME-WEIGHTS: No regime data — returning neutral weights")
            profiles = [
                RegimeWeightProfile(signal_id=sid, effective_weight=cfg.neutral_mult)
                for sid in events_by_signal
            ]
            return AdaptiveWeightReport(
                config=cfg, profiles=profiles,
                total_signals=len(profiles),
            )

        # Current regime = last date
        sorted_dates = sorted(regimes.keys())
        current_regime = regimes[sorted_dates[-1]]

        # Regime distribution
        distribution: dict[str, int] = defaultdict(int)
        for r in regimes.values():
            distribution[r.value] += 1

        # 2. Per-regime performance evaluation
        regime_stats = self._evaluator.evaluate(
            events_by_signal, regimes,
            forward_window=cfg.forward_window,
            min_events=cfg.min_events_per_regime,
        )

        # 3. Compute multipliers + build profiles
        profiles = self._build_profiles(
            events_by_signal, regime_stats, current_regime, cfg,
        )

        # 4. Get base weights from DynamicWeightEngine
        base_weights = self._get_base_weights()
        for p in profiles:
            bw = base_weights.get(p.signal_id, 1.0)
            p.base_weight = round(bw, 4)
            p.effective_weight = round(bw * p.current_multiplier, 4)

        multipliers = [p.current_multiplier for p in profiles]
        avg_mult = sum(multipliers) / max(len(multipliers), 1)

        report = AdaptiveWeightReport(
            config=cfg,
            current_regime=current_regime.value,
            profiles=profiles,
            regime_distribution=dict(distribution),
            total_signals=len(profiles),
            avg_multiplier=round(avg_mult, 4),
        )

        logger.info(
            "REGIME-WEIGHTS: %d signals — regime=%s, avg_mult=%.2f",
            len(profiles), current_regime.value, avg_mult,
        )
        return report

    def get_current_regime(
        self,
        benchmark_ohlcv: pd.DataFrame,
    ) -> str:
        """Detect and return the current market regime."""
        regimes = self._detector.classify(benchmark_ohlcv)
        if not regimes:
            return "unknown"
        sorted_dates = sorted(regimes.keys())
        return regimes[sorted_dates[-1]].value

    def get_effective_weights(
        self,
        report: AdaptiveWeightReport,
    ) -> dict[str, float]:
        """Get {signal_id: effective_weight} from a report."""
        return {p.signal_id: p.effective_weight for p in report.profiles}

    # ── Profile Builder ──────────────────────────────────────────────────

    def _build_profiles(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        regime_stats: dict[str, dict[str, RegimeSignalStats]],
        current_regime: MarketRegime,
        cfg: AdaptiveWeightConfig,
    ) -> list[RegimeWeightProfile]:
        """Build weight profiles with regime multipliers per signal."""
        profiles = []

        for signal_id in events_by_signal:
            stats = regime_stats.get(signal_id, {})

            # Compute multipliers for each regime
            multipliers = self._compute_multipliers(stats, cfg)

            # Apply multipliers back to stats
            for regime_val, mult in multipliers.items():
                if regime_val in stats:
                    stats[regime_val].regime_multiplier = round(mult, 4)

            # Identify best/worst regimes
            valid_regimes = {
                r: s for r, s in stats.items()
                if s.events_count >= cfg.min_events_per_regime
            }
            best_regime = ""
            worst_regime = ""
            if valid_regimes:
                best_regime = max(valid_regimes, key=lambda r: valid_regimes[r].sharpe)
                worst_regime = min(valid_regimes, key=lambda r: valid_regimes[r].sharpe)

            current_mult = multipliers.get(current_regime.value, cfg.neutral_mult)

            profiles.append(RegimeWeightProfile(
                signal_id=signal_id,
                current_regime=current_regime.value,
                current_multiplier=round(current_mult, 4),
                effective_weight=round(current_mult, 4),  # base applied later
                regime_stats=stats,
                best_regime=best_regime,
                worst_regime=worst_regime,
            ))

        return profiles

    def _compute_multipliers(
        self,
        stats: dict[str, RegimeSignalStats],
        cfg: AdaptiveWeightConfig,
    ) -> dict[str, float]:
        """
        Normalise per-regime Sharpe ratios to [min_mult, max_mult].

        Signals with no data for a regime get neutral_mult.
        """
        multipliers: dict[str, float] = {}

        # Collect Sharpe values for regimes with enough data
        sharpe_values: dict[str, float] = {}
        for regime_val, st in stats.items():
            if st.events_count >= cfg.min_events_per_regime:
                sharpe_values[regime_val] = st.sharpe

        if not sharpe_values:
            return {r.value: cfg.neutral_mult for r in MarketRegime}

        min_sharpe = min(sharpe_values.values())
        max_sharpe = max(sharpe_values.values())
        sharpe_range = max_sharpe - min_sharpe

        for regime in MarketRegime:
            rv = regime.value
            if rv not in sharpe_values:
                multipliers[rv] = cfg.neutral_mult
                continue

            if sharpe_range < 1e-8:
                # All regimes have same Sharpe — use neutral
                multipliers[rv] = cfg.neutral_mult
            else:
                # Linear normalisation to [min_mult, max_mult]
                norm = (sharpe_values[rv] - min_sharpe) / sharpe_range
                mult = cfg.min_mult + norm * (cfg.max_mult - cfg.min_mult)
                multipliers[rv] = round(mult, 4)

        return multipliers

    @staticmethod
    def _get_base_weights() -> dict[str, float]:
        """Fetch base weights from DynamicWeightEngine (graceful fallback)."""
        try:
            from src.engines.backtesting.dynamic_weights import DynamicWeightEngine
            engine = DynamicWeightEngine()
            return engine.get_weight_dict()
        except Exception:
            return {}
