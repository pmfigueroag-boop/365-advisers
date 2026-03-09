"""
src/engines/ml_signals/engine.py
──────────────────────────────────────────────────────────────────────────────
ML Signal Factory — orchestrator for end-to-end ML signal generation.

Aggregates feature engineering, training, prediction, and registry
into a single coherent workflow.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.ml_signals.models import (
    MLModelConfig,
    MLSignalOutput,
    ModelCard,
    ModelType,
    SignalDirection,
)
from src.engines.ml_signals.feature_engineering import build_feature_vector
from src.engines.ml_signals.trainer import MLTrainer
from src.engines.ml_signals.predictor import MLPredictor
from src.engines.ml_signals.model_registry import ModelRegistry

logger = logging.getLogger("365advisers.ml_signals.engine")


class MLSignalFactory:
    """
    End-to-end ML signal factory.

    Usage:
        factory = MLSignalFactory()

        # Train
        card, model = factory.train_model(features_matrix, returns, feature_names)

        # Generate signal for a ticker
        signal = factory.generate_signal("AAPL", fundamental_features, technical_features)
    """

    def __init__(self) -> None:
        self.registry = ModelRegistry()
        self._models_cache: dict[str, object] = {}  # model_id → fitted model

    def train_model(
        self,
        features: np.ndarray | list[list[float]],
        target: np.ndarray | list[float],
        feature_names: list[str] | None = None,
        config: MLModelConfig | None = None,
    ) -> ModelCard:
        """
        Train a new ML model and register it.

        Args:
            features: 2D feature matrix (n_samples × n_features).
            target: 1D target array (forward returns).
            feature_names: Optional feature name list.
            config: Training configuration.

        Returns:
            ModelCard with training metrics.
        """
        config = config or MLModelConfig()

        card, model = MLTrainer.train(
            features=features,
            target=target,
            feature_names=feature_names,
            config=config,
        )

        if model is not None:
            # Serialize and register
            model_b64 = MLTrainer.serialize_model(model)
            self.registry.register(card, model_bytes_b64=model_b64)
            self._models_cache[card.model_id] = model
            logger.info("Model trained and registered: %s (acc=%.3f)", card.model_id, card.accuracy)
        else:
            self.registry.register(card)
            logger.warning("Model training failed: %s", card.model_id)

        return card

    def generate_signal(
        self,
        ticker: str,
        fundamental: FundamentalFeatureSet | None = None,
        technical: TechnicalFeatureSet | None = None,
        model_type: ModelType | None = None,
    ) -> MLSignalOutput:
        """
        Generate an ML signal for a single ticker using the deployed model.

        Args:
            ticker: Stock ticker symbol.
            fundamental: Fundamental features (optional).
            technical: Technical features (optional).
            model_type: Specific model type to use (optional, defaults to any deployed).

        Returns:
            MLSignalOutput with prediction, confidence, and direction.
        """
        # Get deployed model
        entry = self.registry.get_deployed(model_type)
        if not entry:
            logger.warning("No deployed model found for type=%s", model_type)
            return MLSignalOutput(
                ticker=ticker,
                direction=SignalDirection.NEUTRAL,
                confidence=0.0,
            )

        # Load model from cache or deserialize
        model = self._models_cache.get(entry.card.model_id)
        if model is None and entry.model_bytes_b64:
            model = MLTrainer.deserialize_model(entry.model_bytes_b64)
            self._models_cache[entry.card.model_id] = model

        if model is None:
            return MLSignalOutput(
                ticker=ticker,
                direction=SignalDirection.NEUTRAL,
                confidence=0.0,
            )

        # Build feature vector
        fv = build_feature_vector(fundamental, technical)
        fv["_ticker"] = ticker  # metadata for output

        # Predict
        signal = MLPredictor.predict(
            model=model,
            feature_vector=fv,
            model_card=entry.card,
        )
        signal.ticker = ticker

        return signal

    def deploy_model(self, model_id: str) -> bool:
        """Deploy a specific model (retires previous of same type)."""
        return self.registry.deploy(model_id)

    def retrain_champion(
        self,
        features: np.ndarray,
        target: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> ModelCard:
        """
        Retrain the currently deployed model's type with new data.

        Automatically deploys if better than the current champion.
        """
        deployed = self.registry.get_deployed()
        config = deployed.card.config if deployed else MLModelConfig()

        new_card = self.train_model(features, target, feature_names, config)

        # Auto-deploy if better
        if deployed and new_card.f1_score > deployed.card.f1_score:
            self.deploy_model(new_card.model_id)
            logger.info(
                "New champion deployed: %s (F1: %.3f → %.3f)",
                new_card.model_id, deployed.card.f1_score, new_card.f1_score,
            )
        elif not deployed:
            self.deploy_model(new_card.model_id)

        return new_card

    def list_models(self, **kwargs) -> list[ModelCard]:
        """List all registered models."""
        return self.registry.list_models(**kwargs)
