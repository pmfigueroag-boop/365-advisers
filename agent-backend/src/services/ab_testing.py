"""
src/services/ab_testing.py
─────────────────────────────────────────────────────────────────────────────
LLM A/B Testing Framework — run prompt optimization experiments.

Supports:
  - Multiple prompt variants per experiment (A/B/C/...)
  - Configurable traffic splits
  - Automatic outcome tracking (latency, tokens, quality)
  - Statistical comparison between variants
"""

from __future__ import annotations

import logging
import random
import time
import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.ab_testing")


# ── Data Models ──────────────────────────────────────────────────────────────

class PromptVariant(BaseModel):
    """A single prompt variant in an experiment."""
    variant_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str                              # e.g. "baseline", "concise_v2"
    prompt_template: str                   # The system prompt text
    model: str = "gemini-2.5-pro"          # LLM model to use
    temperature: float = 0.3


class ExperimentOutcome(BaseModel):
    """Single observation from an experiment run."""
    experiment_id: str
    variant_id: str
    ticker: str = ""
    latency_ms: float = 0.0
    tokens_used: int = 0
    quality_score: float = 0.0             # 0-1, from automated eval
    success: bool = True
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class VariantStats(BaseModel):
    """Aggregated statistics for a variant."""
    variant_id: str
    variant_name: str
    observations: int = 0
    avg_latency_ms: float = 0.0
    avg_tokens: float = 0.0
    avg_quality: float = 0.0
    success_rate: float = 0.0
    p95_latency_ms: float = 0.0


class ExperimentStatus(BaseModel):
    """Full experiment status with per-variant stats."""
    experiment_id: str
    name: str
    status: str                            # "active" | "completed" | "paused"
    variants: list[PromptVariant]
    traffic_split: list[float]
    created_at: datetime
    total_observations: int = 0
    variant_stats: list[VariantStats] = Field(default_factory=list)
    winner: str | None = None


class PromptExperiment(BaseModel):
    """An A/B testing experiment."""
    experiment_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    variants: list[PromptVariant]
    traffic_split: list[float] = Field(default_factory=lambda: [0.5, 0.5])
    status: str = "active"                 # "active" | "completed" | "paused"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    outcomes: list[ExperimentOutcome] = Field(default_factory=list)

    def select_variant(self, seed: str = "") -> PromptVariant:
        """Select a variant based on traffic split (deterministic per seed)."""
        if seed:
            # Deterministic: same seed → same variant (for reproducibility)
            h = int(hashlib.md5(seed.encode()).hexdigest(), 16) % 1000
            threshold = 0.0
            for i, split in enumerate(self.traffic_split):
                threshold += split * 1000
                if h < threshold:
                    return self.variants[i]
            return self.variants[-1]
        else:
            # Random weighted selection
            return random.choices(self.variants, weights=self.traffic_split, k=1)[0]


# ── A/B Testing Engine ───────────────────────────────────────────────────────

class ABTestingEngine:
    """
    Manages LLM prompt experiments.

    Usage:
        engine = ABTestingEngine()
        exp = engine.create_experiment("CIO Prompt v2", variants, [0.5, 0.5])
        variant = engine.select_variant(exp.experiment_id, seed="AAPL")
        # ... run LLM with variant.prompt_template ...
        engine.record_outcome(exp.experiment_id, variant.variant_id,
                              latency_ms=1200, tokens_used=850, quality_score=0.8)
        results = engine.get_results(exp.experiment_id)
    """

    def __init__(self):
        self._experiments: dict[str, PromptExperiment] = {}
        logger.info("ABTestingEngine initialized")

    def create_experiment(
        self,
        name: str,
        variants: list[PromptVariant],
        traffic_split: list[float] | None = None,
        description: str = "",
    ) -> PromptExperiment:
        """Create a new A/B testing experiment."""
        if len(variants) < 2:
            raise ValueError("Need at least 2 variants for an experiment")

        if traffic_split is None:
            traffic_split = [1.0 / len(variants)] * len(variants)

        if len(traffic_split) != len(variants):
            raise ValueError("traffic_split must match number of variants")

        if abs(sum(traffic_split) - 1.0) > 0.01:
            raise ValueError("traffic_split must sum to 1.0")

        experiment = PromptExperiment(
            name=name,
            description=description,
            variants=variants,
            traffic_split=traffic_split,
        )
        self._experiments[experiment.experiment_id] = experiment
        logger.info(
            "Created experiment '%s' (%s) with %d variants",
            name, experiment.experiment_id[:8], len(variants),
        )
        return experiment

    def list_experiments(self, status: str | None = None) -> list[ExperimentStatus]:
        """List all experiments, optionally filtered by status."""
        results = []
        for exp in self._experiments.values():
            if status and exp.status != status:
                continue
            results.append(self._build_status(exp))
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def get_experiment(self, experiment_id: str) -> PromptExperiment | None:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    def select_variant(
        self, experiment_id: str, seed: str = "",
    ) -> PromptVariant | None:
        """Select a variant for a given experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != "active":
            return None
        return exp.select_variant(seed)

    def record_outcome(
        self,
        experiment_id: str,
        variant_id: str,
        latency_ms: float = 0.0,
        tokens_used: int = 0,
        quality_score: float = 0.0,
        success: bool = True,
        ticker: str = "",
        metadata: dict | None = None,
    ) -> bool:
        """Record the outcome of a single experiment run."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return False

        outcome = ExperimentOutcome(
            experiment_id=experiment_id,
            variant_id=variant_id,
            ticker=ticker,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            quality_score=quality_score,
            success=success,
            metadata=metadata or {},
        )
        exp.outcomes.append(outcome)
        return True

    def get_results(self, experiment_id: str) -> ExperimentStatus | None:
        """Get full results for an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return None
        return self._build_status(exp)

    def complete_experiment(self, experiment_id: str) -> ExperimentStatus | None:
        """Mark an experiment as completed, determine winner."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return None
        exp.status = "completed"
        status = self._build_status(exp)

        # Determine winner by highest quality score (with min observations)
        valid = [s for s in status.variant_stats if s.observations >= 5]
        if valid:
            winner = max(valid, key=lambda s: s.avg_quality)
            status.winner = winner.variant_id
            logger.info(
                "Experiment '%s' completed — winner: %s (quality=%.2f)",
                exp.name, winner.variant_name, winner.avg_quality,
            )
        return status

    def pause_experiment(self, experiment_id: str) -> bool:
        """Pause an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return False
        exp.status = "paused"
        return True

    def resume_experiment(self, experiment_id: str) -> bool:
        """Resume a paused experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != "paused":
            return False
        exp.status = "active"
        return True

    def _build_status(self, exp: PromptExperiment) -> ExperimentStatus:
        """Build aggregated status for an experiment."""
        variant_stats = []
        for variant in exp.variants:
            outcomes = [o for o in exp.outcomes if o.variant_id == variant.variant_id]
            n = len(outcomes)
            if n == 0:
                variant_stats.append(VariantStats(
                    variant_id=variant.variant_id,
                    variant_name=variant.name,
                ))
                continue

            latencies = [o.latency_ms for o in outcomes]
            latencies.sort()

            variant_stats.append(VariantStats(
                variant_id=variant.variant_id,
                variant_name=variant.name,
                observations=n,
                avg_latency_ms=round(sum(latencies) / n, 1),
                avg_tokens=round(sum(o.tokens_used for o in outcomes) / n, 1),
                avg_quality=round(sum(o.quality_score for o in outcomes) / n, 3),
                success_rate=round(sum(1 for o in outcomes if o.success) / n, 3),
                p95_latency_ms=round(latencies[int(n * 0.95)] if n >= 20 else latencies[-1], 1),
            ))

        return ExperimentStatus(
            experiment_id=exp.experiment_id,
            name=exp.name,
            status=exp.status,
            variants=exp.variants,
            traffic_split=exp.traffic_split,
            created_at=exp.created_at,
            total_observations=len(exp.outcomes),
            variant_stats=variant_stats,
        )


# Singleton
_ab_engine = ABTestingEngine()


def get_ab_engine() -> ABTestingEngine:
    return _ab_engine
