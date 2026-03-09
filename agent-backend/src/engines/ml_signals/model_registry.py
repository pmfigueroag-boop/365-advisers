"""
src/engines/ml_signals/model_registry.py
──────────────────────────────────────────────────────────────────────────────
Model lifecycle registry.

Manages model registration, deployment, retirement, and comparison.
Uses in-memory storage (same pattern as EventCalendar).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.ml_signals.models import (
    ModelCard,
    ModelRegistryEntry,
    ModelStatus,
    ModelType,
)

logger = logging.getLogger("365advisers.ml_signals.registry")


class ModelRegistry:
    """
    In-memory model registry for ML signal models.

    Manages model lifecycle:
        register → ready → deployed → retired

    Only one model per ModelType can be DEPLOYED at a time.
    """

    def __init__(self) -> None:
        self._models: dict[str, ModelRegistryEntry] = {}

    # ── Registration ─────────────────────────────────────────────────────

    def register(
        self,
        card: ModelCard,
        model_bytes_b64: str = "",
    ) -> str:
        """Register a trained model. Returns model_id."""
        entry = ModelRegistryEntry(
            card=card,
            model_bytes_b64=model_bytes_b64,
        )
        self._models[card.model_id] = entry
        logger.info("Model registered: %s (%s)", card.model_id, card.model_type.value)
        return card.model_id

    # ── Deployment ───────────────────────────────────────────────────────

    def deploy(self, model_id: str) -> bool:
        """
        Deploy a model (retire any existing deployed model of same type).

        Returns True if successful.
        """
        entry = self._models.get(model_id)
        if not entry:
            logger.warning("Model not found: %s", model_id)
            return False

        if entry.card.status not in (ModelStatus.READY, ModelStatus.DEPLOYED):
            logger.warning("Cannot deploy model in status: %s", entry.card.status)
            return False

        # Retire previous deployed model of same type
        for mid, e in self._models.items():
            if (
                e.card.model_type == entry.card.model_type
                and e.card.status == ModelStatus.DEPLOYED
                and mid != model_id
            ):
                e.card.status = ModelStatus.RETIRED
                logger.info("Retired previous model: %s", mid)

        entry.card.status = ModelStatus.DEPLOYED
        logger.info("Model deployed: %s", model_id)
        return True

    def retire(self, model_id: str) -> bool:
        """Retire a model."""
        entry = self._models.get(model_id)
        if not entry:
            return False
        entry.card.status = ModelStatus.RETIRED
        logger.info("Model retired: %s", model_id)
        return True

    # ── Queries ───────────────────────────────────────────────────────────

    def get(self, model_id: str) -> ModelRegistryEntry | None:
        """Get a specific model entry."""
        return self._models.get(model_id)

    def get_card(self, model_id: str) -> ModelCard | None:
        """Get a model card by ID."""
        entry = self._models.get(model_id)
        return entry.card if entry else None

    def get_deployed(self, model_type: ModelType | None = None) -> ModelRegistryEntry | None:
        """Get the currently deployed model of a given type (or any)."""
        for entry in self._models.values():
            if entry.card.status != ModelStatus.DEPLOYED:
                continue
            if model_type is None or entry.card.model_type == model_type:
                return entry
        return None

    def list_models(
        self,
        status: ModelStatus | None = None,
        model_type: ModelType | None = None,
    ) -> list[ModelCard]:
        """List model cards, optionally filtered by status and type."""
        results = []
        for entry in self._models.values():
            if status and entry.card.status != status:
                continue
            if model_type and entry.card.model_type != model_type:
                continue
            results.append(entry.card)
        return sorted(results, key=lambda c: c.trained_at, reverse=True)

    # ── Comparison ───────────────────────────────────────────────────────

    def compare(self, model_id_a: str, model_id_b: str) -> dict:
        """Compare two models side-by-side."""
        a = self.get_card(model_id_a)
        b = self.get_card(model_id_b)
        if not a or not b:
            return {"error": "One or both models not found"}

        return {
            "model_a": {
                "model_id": a.model_id,
                "type": a.model_type.value,
                "accuracy": a.accuracy,
                "precision": a.precision,
                "recall": a.recall,
                "f1_score": a.f1_score,
                "ic": a.information_coefficient,
                "hit_rate": a.hit_rate,
                "features": a.feature_count,
                "samples": a.training_samples,
            },
            "model_b": {
                "model_id": b.model_id,
                "type": b.model_type.value,
                "accuracy": b.accuracy,
                "precision": b.precision,
                "recall": b.recall,
                "f1_score": b.f1_score,
                "ic": b.information_coefficient,
                "hit_rate": b.hit_rate,
                "features": b.feature_count,
                "samples": b.training_samples,
            },
            "winner": model_id_a if a.f1_score >= b.f1_score else model_id_b,
            "advantage_metric": "f1_score",
        }

    @property
    def total_models(self) -> int:
        return len(self._models)
