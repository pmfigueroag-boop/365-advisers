"""
src/engines/signal_discovery/engine.py
──────────────────────────────────────────────────────────────────────────────
Signal Discovery Engine — orchestrator.

Pipeline:
  1. Generate candidate signals from features
  2. Evaluate predictive power (IC, hit rate, Sharpe)
  3. Filter by stability and statistical significance
  4. Return promoted candidates
"""

from __future__ import annotations

import logging

from src.engines.signal_discovery.evaluator import CandidateEvaluator
from src.engines.signal_discovery.generator import FeatureGenerator
from src.engines.signal_discovery.models import (
    CandidateSignal,
    CandidateStatus,
    DiscoveryConfig,
    DiscoveryReport,
)

logger = logging.getLogger("365advisers.signal_discovery.engine")


class SignalDiscoveryEngine:
    """
    Discovers new signals from feature combinations.

    Usage::

        engine = SignalDiscoveryEngine()
        report = engine.discover(signal_values, forward_returns)
    """

    def __init__(self, config: DiscoveryConfig | None = None) -> None:
        self.config = config or DiscoveryConfig()
        self._generator = FeatureGenerator(self.config)
        self._evaluator = CandidateEvaluator()

    def discover(
        self,
        signal_values: dict[str, list[float]],
        forward_returns: list[float],
        features: list[str] | None = None,
        config: DiscoveryConfig | None = None,
    ) -> DiscoveryReport:
        """
        Run full discovery pipeline.

        Parameters
        ----------
        signal_values : dict
            {candidate_id: [values]} — pre-computed values for each candidate.
            If empty, generator creates candidates and values are expected
            to be provided externally.
        forward_returns : list[float]
            Forward returns aligned to data.
        features : list[str] | None
            Feature paths. If None, uses defaults.
        config : DiscoveryConfig | None

        Returns
        -------
        DiscoveryReport
        """
        cfg = config or self.config

        # Stage 1: Generate candidates
        candidates = self._generator.generate(features)
        total_generated = len(candidates)

        # Stage 2+3+4: Evaluate, stability, spurious check
        evaluated = self._evaluator.evaluate(
            candidates, signal_values, forward_returns, cfg,
        )

        promoted = [c for c in evaluated if c.status == CandidateStatus.PROMOTED.value]
        rejected = [c for c in evaluated if c.status == CandidateStatus.REJECTED.value]

        # Sort promoted by IC descending
        promoted.sort(key=lambda c: abs(c.information_coefficient), reverse=True)

        report = DiscoveryReport(
            config=cfg,
            candidates=promoted + rejected,
            total_generated=total_generated,
            total_evaluated=len(evaluated),
            total_stable=sum(1 for c in evaluated if c.stability >= cfg.min_stability),
            total_promoted=len(promoted),
            total_rejected=len(rejected),
        )

        logger.info(
            "DISCOVERY: %d generated → %d evaluated → %d promoted",
            total_generated, len(evaluated), len(promoted),
        )
        return report

    def discover_from_candidates(
        self,
        candidates: list[CandidateSignal],
        signal_values: dict[str, list[float]],
        forward_returns: list[float],
        config: DiscoveryConfig | None = None,
    ) -> DiscoveryReport:
        """
        Evaluate pre-generated candidates (skip generator stage).
        """
        cfg = config or self.config

        evaluated = self._evaluator.evaluate(
            candidates, signal_values, forward_returns, cfg,
        )

        promoted = [c for c in evaluated if c.status == CandidateStatus.PROMOTED.value]
        rejected = [c for c in evaluated if c.status == CandidateStatus.REJECTED.value]
        promoted.sort(key=lambda c: abs(c.information_coefficient), reverse=True)

        return DiscoveryReport(
            config=cfg,
            candidates=promoted + rejected,
            total_generated=len(candidates),
            total_evaluated=len(evaluated),
            total_stable=sum(1 for c in evaluated if c.stability >= cfg.min_stability),
            total_promoted=len(promoted),
            total_rejected=len(rejected),
        )
