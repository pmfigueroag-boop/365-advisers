"""
src/engines/experiment_tracking/hooks.py
─────────────────────────────────────────────────────────────────────────────
ExperimentHook — auto-registration helper for research engines.

Provides a context-manager pattern for engines to automatically
register, run, and record experiments.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    ResearchExperimentCreate,
    ResearchExperimentType,
    compute_data_fingerprint,
)
from .tracker import ResearchExperimentTracker

logger = logging.getLogger("365advisers.experiment_tracking.hooks")


class ExperimentHook:
    """Auto-registration helper for research engines.

    Usage:
        hook = ExperimentHook.start(
            experiment_type="strategy_research",
            name="Momentum Backtest",
            config=strategy_config,
            data=data_bundle,
        )
        try:
            result = engine.run(...)
            hook.complete(result.get("metrics", {}))
        except Exception as e:
            hook.fail(str(e))
    """

    def __init__(self, experiment_id: str):
        self.experiment_id = experiment_id

    @staticmethod
    def start(
        experiment_type: str,
        name: str,
        config: dict | None = None,
        data: dict | None = None,
        description: str = "",
        hypothesis: str = "",
        tags: list[str] | None = None,
        author: str = "system",
        parent_experiment_id: str | None = None,
    ) -> ExperimentHook:
        """Start tracking an experiment.

        Registers the experiment and marks it as running.
        Returns an ExperimentHook for completing/failing.
        """
        fp = compute_data_fingerprint(data) if data else ""

        exp_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
            experiment_type=ResearchExperimentType(experiment_type),
            name=name,
            description=description,
            hypothesis=hypothesis,
            tags=tags or [],
            author=author,
            config_snapshot=config or {},
            data_fingerprint=fp,
            parent_experiment_id=parent_experiment_id,
        ))

        ResearchExperimentTracker.mark_running(exp_id)
        logger.info("Experiment hook started: %s (%s)", exp_id, name)

        return ExperimentHook(exp_id)

    def complete(self, metrics: dict[str, Any] | None = None) -> str:
        """Mark the experiment as completed with metrics."""
        ResearchExperimentTracker.mark_completed(self.experiment_id, metrics)

        if metrics:
            ResearchExperimentTracker.attach_artifact(
                self.experiment_id, "metrics", metrics,
            )

        logger.info("Experiment completed: %s", self.experiment_id)
        return self.experiment_id

    def fail(self, error: str = "") -> str:
        """Mark the experiment as failed."""
        ResearchExperimentTracker.mark_failed(self.experiment_id, error)
        logger.warning("Experiment failed: %s — %s", self.experiment_id, error)
        return self.experiment_id

    def attach(self, artifact_type: str, payload: dict) -> None:
        """Attach an artifact to the experiment."""
        ResearchExperimentTracker.attach_artifact(
            self.experiment_id, artifact_type, payload,
        )
