"""
src/engines/experiment_tracking/reproducibility.py
─────────────────────────────────────────────────────────────────────────────
ReproducibilityEngine — reproduce past experiments with frozen configs.

Ensures:
  - Data fingerprint verification
  - Config freeze + restore
  - Result drift measurement
"""

from __future__ import annotations

import logging
from typing import Any

from .models import ReproductionResult, compute_data_fingerprint
from .tracker import ResearchExperimentTracker

logger = logging.getLogger("365advisers.experiment_tracking.reproducibility")


class ReproducibilityEngine:
    """Reproduce past experiments and measure result drift."""

    @staticmethod
    def reproduce(
        original_experiment_id: str,
        data: dict,
        run_fn: Any = None,
    ) -> ReproductionResult:
        """Reproduce an experiment.

        Args:
            original_experiment_id: ID of the experiment to reproduce.
            data: Data bundle to use for reproduction.
            run_fn: Optional callable(config, data) → result.
                     If None, returns a dry-run reproduction check.

        Returns:
            ReproductionResult with drift analysis.
        """
        original = ResearchExperimentTracker.get(original_experiment_id)
        if not original:
            return ReproductionResult(
                original_experiment_id=original_experiment_id,
                reproduction_experiment_id="",
                reproduction_status="error: original not found",
            )

        # ── Verify data fingerprint ──
        current_fp = compute_data_fingerprint(data)
        original_fp = original.data_fingerprint
        fp_match = current_fp == original_fp if original_fp else True

        # ── Config match ──
        config = original.config_snapshot
        config_match = bool(config)  # True if we have a config to reproduce

        if run_fn is None:
            # Dry run — just verify reproducibility potential
            return ReproductionResult(
                original_experiment_id=original_experiment_id,
                reproduction_experiment_id="dry_run",
                data_fingerprint_match=fp_match,
                config_match=config_match,
                reproduction_status="dry_run" if fp_match and config_match else "cannot_reproduce",
            )

        # ── Re-execute ──
        from .models import ResearchExperimentCreate, ResearchExperimentType

        # Register reproduction as child experiment
        repro_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
            experiment_type=ResearchExperimentType(original.experiment_type),
            name=f"Reproduction of {original.name}",
            description=f"Reproduction of experiment {original_experiment_id}",
            hypothesis=f"Verify reproducibility of {original.name}",
            tags=["reproduction", "verification"],
            config_snapshot=config,
            data_fingerprint=current_fp,
            parent_experiment_id=original_experiment_id,
        ))

        ResearchExperimentTracker.mark_running(repro_id)

        try:
            result = run_fn(config, data)
            new_metrics = result.get("metrics", {}) if isinstance(result, dict) else {}
            ResearchExperimentTracker.mark_completed(repro_id, metrics=new_metrics)
        except Exception as e:
            ResearchExperimentTracker.mark_failed(repro_id, str(e))
            return ReproductionResult(
                original_experiment_id=original_experiment_id,
                reproduction_experiment_id=repro_id,
                data_fingerprint_match=fp_match,
                config_match=config_match,
                reproduction_status=f"failed: {str(e)}",
            )

        # ── Measure drift ──
        original_metrics = original.metrics
        metric_drift = {}
        for key in set(list(original_metrics.keys()) + list(new_metrics.keys())):
            old_val = original_metrics.get(key)
            new_val = new_metrics.get(key)
            if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                drift = abs(new_val - old_val)
                metric_drift[key] = round(drift, 6)

        # Determine status
        max_drift = max(metric_drift.values()) if metric_drift else 0
        if max_drift == 0:
            status = "exact_match"
        elif max_drift < 0.01:
            status = "close_match"
        else:
            status = "diverged"

        return ReproductionResult(
            original_experiment_id=original_experiment_id,
            reproduction_experiment_id=repro_id,
            data_fingerprint_match=fp_match,
            config_match=config_match,
            metric_drift=metric_drift,
            reproduction_status=status,
        )

    @staticmethod
    def check_reproducibility(experiment_id: str, data: dict | None = None) -> dict:
        """Check if an experiment can be reproduced.

        Returns reproducibility assessment without actually re-running.
        """
        original = ResearchExperimentTracker.get(experiment_id)
        if not original:
            return {"reproducible": False, "reason": "Experiment not found"}

        issues = []

        if not original.config_snapshot:
            issues.append("No config snapshot available")

        if not original.metrics:
            issues.append("No metrics recorded — cannot compare results")

        if data and original.data_fingerprint:
            current_fp = compute_data_fingerprint(data)
            if current_fp != original.data_fingerprint:
                issues.append(f"Data fingerprint mismatch: {original.data_fingerprint} vs {current_fp}")

        return {
            "experiment_id": experiment_id,
            "reproducible": len(issues) == 0,
            "issues": issues,
            "has_config": bool(original.config_snapshot),
            "has_metrics": bool(original.metrics),
            "has_fingerprint": bool(original.data_fingerprint),
        }
