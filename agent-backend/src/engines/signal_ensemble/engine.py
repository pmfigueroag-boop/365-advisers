"""
src/engines/signal_ensemble/engine.py
──────────────────────────────────────────────────────────────────────────────
Ensemble Intelligence Engine — orchestrator.

Pipeline:
  1. Detect co-firing signal pairs (and optionally triplets)
  2. Score synergy for each combination
  3. Evaluate temporal stability
  4. Rank and select top ensembles
  5. Compute ensemble bonus for CASE integration
"""

from __future__ import annotations

import logging

from src.engines.backtesting.models import SignalEvent
from src.engines.signal_ensemble.co_fire import CoFireAnalyzer
from src.engines.signal_ensemble.models import (
    EnsembleConfig,
    EnsembleReport,
    SignalCombination,
)
from src.engines.signal_ensemble.stability import StabilityAnalyzer
from src.engines.signal_ensemble.synergy import SynergyScorer

logger = logging.getLogger("365advisers.signal_ensemble.engine")


class EnsembleIntelligenceEngine:
    """
    Analyzes signal library for synergistic combinations.

    Usage::

        engine = EnsembleIntelligenceEngine()
        report = engine.analyze(events_by_signal)
        bonus = engine.get_ensemble_bonus(report, active_signals)
    """

    def __init__(self, config: EnsembleConfig | None = None) -> None:
        self.config = config or EnsembleConfig()

    # ── Public API ────────────────────────────────────────────────────────

    def analyze(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        config: EnsembleConfig | None = None,
    ) -> EnsembleReport:
        """
        Run full ensemble discovery pipeline.

        Parameters
        ----------
        events_by_signal : dict
            {signal_id: [SignalEvent, ...]}
        config : EnsembleConfig | None
            Override configuration.

        Returns
        -------
        EnsembleReport
        """
        cfg = config or self.config

        co_fire = CoFireAnalyzer(date_tolerance=cfg.date_tolerance)
        synergy = SynergyScorer()
        stability = StabilityAnalyzer(
            window_months=cfg.stability_window_months,
            stride_months=cfg.stability_stride_months,
        )

        # 1. Detect co-firing pairs
        pairs = co_fire.detect_pairs(
            events_by_signal, cfg.forward_window, cfg.min_co_fires,
        )

        # 2. Score synergy for each pair
        combinations: list[SignalCombination] = []
        for (sig_a, sig_b), co_fires in pairs.items():
            combo = synergy.score(
                [sig_a, sig_b], co_fires,
                events_by_signal, cfg.forward_window,
            )
            combinations.append(combo)

        # 3. Optionally extend to triplets
        if cfg.max_combo_size >= 3:
            synergistic_pairs = {
                k: v for k, v in pairs.items()
                if any(c.synergy_score > cfg.min_synergy
                       for c in combinations
                       if set(c.signals) == set(k))
            }
            triplets = co_fire.detect_triplets(
                synergistic_pairs, events_by_signal,
                cfg.forward_window, cfg.min_co_fires,
            )
            for signals, co_fires in triplets.items():
                combo = synergy.score(
                    list(signals), co_fires,
                    events_by_signal, cfg.forward_window,
                )
                combinations.append(combo)

        # 4. Evaluate stability for synergistic combos
        synergistic = [
            c for c in combinations if c.synergy_score > cfg.min_synergy
        ]

        for combo in synergistic:
            # Get co-fires for this combo
            key = tuple(sorted(combo.signals))
            co_fires = pairs.get(key[:2], [])
            if len(key) == 2:
                co_fires = pairs.get(key, [])

            stab, stable_w, total_w = stability.evaluate(
                co_fires, combo.max_individual_sharpe,
            )
            combo.stability = stab
            combo.stable_windows = stable_w
            combo.total_windows = total_w

            # Ensemble score = synergy × stability × (1 + IPP)
            combo.ensemble_score = round(
                combo.synergy_score * combo.stability * (1 + max(0, combo.incremental_power)),
                4,
            )

        # 5. Select top ensembles
        stable_ensembles = [
            c for c in synergistic if c.stability >= cfg.min_stability
        ]
        stable_ensembles.sort(key=lambda c: c.ensemble_score, reverse=True)
        top = stable_ensembles[:cfg.max_ensembles]

        synergistic_count = len(synergistic)

        report = EnsembleReport(
            config=cfg,
            combinations=combinations,
            top_ensembles=top,
            total_pairs_analyzed=len(combinations),
            synergistic_pairs=synergistic_count,
            stable_ensembles=len(stable_ensembles),
        )

        logger.info(
            "ENSEMBLE: %d pairs analyzed → %d synergistic → %d stable → top %d",
            len(combinations), synergistic_count,
            len(stable_ensembles), len(top),
        )
        return report

    def get_ensemble_bonus(
        self,
        report: EnsembleReport,
        active_signals: list[str],
    ) -> float:
        """
        Compute CASE bonus when active signals match a known ensemble.

        Parameters
        ----------
        report : EnsembleReport
            Previously computed ensemble analysis.
        active_signals : list[str]
            Signal IDs currently active for a ticker.

        Returns
        -------
        float
            Bonus in [0, ensemble_bonus_cap].
        """
        if not report.top_ensembles or not active_signals:
            return 0.0

        active_set = set(active_signals)
        best_bonus = 0.0

        for ensemble in report.top_ensembles:
            ens_set = set(ensemble.signals)
            overlap = active_set & ens_set
            if not overlap:
                continue

            coverage = len(overlap) / len(ens_set)
            if coverage < 0.5:
                continue  # Need at least half the ensemble active

            bonus = ensemble.ensemble_score * coverage
            best_bonus = max(best_bonus, bonus)

        return round(min(best_bonus, report.config.ensemble_bonus_cap), 4)
