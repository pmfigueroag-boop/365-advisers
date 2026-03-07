"""
src/engines/signal_selection/engine.py
──────────────────────────────────────────────────────────────────────────────
Redundancy Pruning Engine — orchestrator.

Pipeline:
  1. Build pairwise Pearson correlation matrix
  2. Estimate mutual information for high-correlation pairs
  3. Compute leave-one-out incremental alpha
  4. Score + classify each signal (KEEP / REDUCE / CANDIDATE / REMOVE)
  5. Optionally apply to SignalRegistry (auto-disable)
"""

from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np

from src.engines.backtesting.models import SignalEvent
from src.engines.signal_selection.correlation import CorrelationAnalyzer
from src.engines.signal_selection.incremental import IncrementalAlphaAnalyzer
from src.engines.signal_selection.models import (
    RedundancyClass,
    RedundancyConfig,
    RedundancyReport,
    SignalPairAnalysis,
    SignalRedundancyProfile,
)
from src.engines.signal_selection.mutual_info import MutualInfoEstimator

logger = logging.getLogger("365advisers.signal_selection.engine")


class RedundancyPruningEngine:
    """
    Analyzes signal library for redundancy and recommends pruning.

    Usage::

        engine = RedundancyPruningEngine()
        report = engine.analyze(events_by_signal)
    """

    def __init__(self, config: RedundancyConfig | None = None) -> None:
        self.config = config or RedundancyConfig()
        self._corr = CorrelationAnalyzer()
        self._mi = MutualInfoEstimator(n_bins=self.config.mi_bins)
        self._inc = IncrementalAlphaAnalyzer()

    # ── Public API ────────────────────────────────────────────────────────

    def analyze(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        config: RedundancyConfig | None = None,
    ) -> RedundancyReport:
        """
        Run full redundancy analysis.

        Parameters
        ----------
        events_by_signal : dict
            {signal_id: [SignalEvent, ...]}
        config : RedundancyConfig | None
            Override configuration.

        Returns
        -------
        RedundancyReport
        """
        cfg = config or self.config
        window = cfg.forward_window

        # 1. Correlation matrix
        corr_matrix = self._corr.compute_matrix(
            events_by_signal, window, cfg.min_overlap,
        )

        # 2. Pair analyses + MI for high-corr pairs
        pair_analyses = self._analyze_pairs(
            events_by_signal, corr_matrix, cfg,
        )

        # 3. Incremental alpha
        incr_alpha = self._inc.compute(events_by_signal, window)

        # 4. Build per-signal profiles
        profiles = self._build_profiles(
            events_by_signal, corr_matrix, pair_analyses,
            incr_alpha, cfg,
        )

        # Sort by redundancy score descending
        profiles.sort(key=lambda p: p.redundancy_score, reverse=True)

        # 5. Classification buckets
        keep = [p.signal_id for p in profiles if p.classification == RedundancyClass.KEEP]
        reduce = [p.signal_id for p in profiles if p.classification == RedundancyClass.REDUCE_WEIGHT]
        candidate = [p.signal_id for p in profiles if p.classification == RedundancyClass.CANDIDATE_REMOVAL]
        remove = [p.signal_id for p in profiles if p.classification == RedundancyClass.REMOVE]

        redundant_pairs = sum(1 for pa in pair_analyses if pa.redundant)
        scores = [p.redundancy_score for p in profiles]
        avg_score = sum(scores) / max(len(scores), 1)

        report = RedundancyReport(
            config=cfg,
            profiles=profiles,
            correlation_matrix=corr_matrix,
            pair_analyses=pair_analyses,
            keep_signals=keep,
            reduce_signals=reduce,
            candidate_removal=candidate,
            remove_signals=remove,
            total_signals=len(profiles),
            total_redundancy_pairs=redundant_pairs,
            avg_redundancy_score=round(avg_score, 4),
        )

        logger.info(
            "SELECTION: %d signals — KEEP=%d, REDUCE=%d, CANDIDATE=%d, REMOVE=%d",
            len(profiles), len(keep), len(reduce), len(candidate), len(remove),
        )
        return report

    def apply_to_registry(
        self,
        report: RedundancyReport,
        auto_disable: bool = True,
    ) -> dict[str, str]:
        """
        Apply pruning recommendations to the SignalRegistry.

        Returns {signal_id: action_taken}
        """
        from src.engines.alpha_signals.registry import registry

        actions: dict[str, str] = {}
        for p in report.profiles:
            if p.classification == RedundancyClass.REMOVE and auto_disable:
                registry.disable(p.signal_id)
                actions[p.signal_id] = "disabled"
            elif p.classification == RedundancyClass.REDUCE_WEIGHT:
                actions[p.signal_id] = f"reduce_weight_to_{p.recommended_weight:.2f}"
            elif p.classification == RedundancyClass.CANDIDATE_REMOVAL:
                actions[p.signal_id] = "flagged_for_review"
            else:
                actions[p.signal_id] = "keep"

        logger.info(
            "SELECTION: Applied to registry — %d disabled, %d reduced",
            sum(1 for v in actions.values() if v == "disabled"),
            sum(1 for v in actions.values() if "reduce" in v),
        )
        return actions

    def get_recommended_weights(
        self,
        report: RedundancyReport,
    ) -> dict[str, float]:
        """Get weight multipliers for DynamicWeightEngine integration."""
        return {p.signal_id: p.recommended_weight for p in report.profiles}

    # ── Pair Analysis ────────────────────────────────────────────────────

    def _analyze_pairs(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        corr_matrix: dict[str, dict[str, float]],
        cfg: RedundancyConfig,
    ) -> list[SignalPairAnalysis]:
        """Analyze all signal pairs: correlation + MI for high-corr pairs."""
        from itertools import combinations

        signal_ids = sorted(events_by_signal.keys())
        pairs: list[SignalPairAnalysis] = []

        for sig_a, sig_b in combinations(signal_ids, 2):
            rho = corr_matrix.get(sig_a, {}).get(sig_b, 0.0)
            abs_rho = abs(rho)

            # Only compute MI for moderately+ correlated pairs
            mi_val = 0.0
            if abs_rho >= 0.30:
                rets_a, rets_b = self._get_paired_returns(
                    events_by_signal[sig_a],
                    events_by_signal[sig_b],
                    cfg.forward_window,
                )
                if len(rets_a) >= cfg.min_overlap:
                    mi_val = self._mi.estimate(
                        np.array(rets_a), np.array(rets_b),
                    )

            redundant = abs_rho >= cfg.corr_threshold

            pairs.append(SignalPairAnalysis(
                signal_a=sig_a,
                signal_b=sig_b,
                correlation=round(rho, 6),
                abs_correlation=round(abs_rho, 6),
                mutual_information=mi_val,
                overlap_count=0,
                redundant=redundant,
            ))

        return pairs

    def _get_paired_returns(
        self,
        events_a: list[SignalEvent],
        events_b: list[SignalEvent],
        window: int,
    ) -> tuple[list[float], list[float]]:
        """Get paired returns for MI estimation."""
        # Index by ticker+date
        index_b: dict[str, dict] = defaultdict(dict)
        for e in events_b:
            r = e.forward_returns.get(window)
            if r is not None:
                index_b[e.ticker][str(e.fired_date)] = r

        rets_a, rets_b = [], []
        for e in events_a:
            r_a = e.forward_returns.get(window)
            if r_a is None:
                continue
            r_b = index_b.get(e.ticker, {}).get(str(e.fired_date))
            if r_b is not None:
                rets_a.append(r_a)
                rets_b.append(r_b)

        return rets_a, rets_b

    # ── Profile Builder ──────────────────────────────────────────────────

    def _build_profiles(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        corr_matrix: dict[str, dict[str, float]],
        pair_analyses: list[SignalPairAnalysis],
        incr_alpha: dict[str, float],
        cfg: RedundancyConfig,
    ) -> list[SignalRedundancyProfile]:
        """Build redundancy profile for each signal."""
        # Pre-compute per-signal MI maxes
        mi_by_signal: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for pa in pair_analyses:
            mi_by_signal[pa.signal_a].append((pa.signal_b, pa.mutual_information))
            mi_by_signal[pa.signal_b].append((pa.signal_a, pa.mutual_information))

        profiles = []
        signal_ids = sorted(events_by_signal.keys())

        for sig_id in signal_ids:
            # Correlation stats
            corr_row = corr_matrix.get(sig_id, {})
            others = {k: abs(v) for k, v in corr_row.items() if k != sig_id}
            max_corr = max(others.values()) if others else 0.0
            max_corr_partner = max(others, key=others.get) if others else ""
            avg_abs_corr = sum(others.values()) / max(len(others), 1) if others else 0.0

            # Rank by correlation
            sorted_partners = sorted(others.items(), key=lambda x: x[1], reverse=True)
            most_correlated = [k for k, _ in sorted_partners[:5]]

            # MI stats
            mi_list = mi_by_signal.get(sig_id, [])
            max_mi = max((v for _, v in mi_list), default=0.0)
            max_mi_partner = ""
            for partner, val in mi_list:
                if val == max_mi:
                    max_mi_partner = partner
                    break

            # Incremental alpha
            inc_a = incr_alpha.get(sig_id, 0.0)

            # Normalise incremental alpha to [0, 1]
            all_inc = list(incr_alpha.values())
            max_inc = max(abs(v) for v in all_inc) if all_inc else 1.0
            norm_inc = (inc_a / max_inc) if max_inc > 0 else 0.0
            norm_inc = max(0.0, min(norm_inc, 1.0))

            # Redundancy score
            score = (
                cfg.w_corr * max_corr
                + cfg.w_mi * max_mi
                - cfg.w_alpha * norm_inc
            )
            score = max(0.0, min(score, 1.0))

            # Classify
            classification = self._classify(score, cfg)

            # Recommended weight
            if classification == RedundancyClass.REMOVE:
                rec_weight = 0.0
            elif classification == RedundancyClass.CANDIDATE_REMOVAL:
                rec_weight = cfg.weight_reduction_factor * 0.5
            elif classification == RedundancyClass.REDUCE_WEIGHT:
                rec_weight = cfg.weight_reduction_factor
            else:
                rec_weight = 1.0

            profiles.append(SignalRedundancyProfile(
                signal_id=sig_id,
                max_correlation=round(max_corr, 6),
                max_corr_partner=max_corr_partner,
                avg_abs_correlation=round(avg_abs_corr, 6),
                max_mi=round(max_mi, 6),
                max_mi_partner=max_mi_partner,
                incremental_alpha=round(inc_a, 6),
                redundancy_score=round(score, 4),
                classification=classification,
                recommended_weight=round(rec_weight, 4),
                most_correlated=most_correlated,
                total_events=len(events_by_signal.get(sig_id, [])),
            ))

        return profiles

    @staticmethod
    def _classify(score: float, cfg: RedundancyConfig) -> RedundancyClass:
        """Classify signal based on redundancy score and thresholds."""
        if score >= cfg.auto_disable_threshold:
            return RedundancyClass.REMOVE
        if score >= cfg.candidate_threshold:
            return RedundancyClass.CANDIDATE_REMOVAL
        if score >= cfg.reduce_threshold:
            return RedundancyClass.REDUCE_WEIGHT
        return RedundancyClass.KEEP
