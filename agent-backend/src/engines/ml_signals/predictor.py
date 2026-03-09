"""
src/engines/ml_signals/predictor.py
──────────────────────────────────────────────────────────────────────────────
ML model inference and signal generation.

Takes a fitted model + feature vector and produces a calibrated
MLSignalOutput with confidence scoring and direction classification.
"""

from __future__ import annotations

import logging

import numpy as np

from src.engines.ml_signals.models import (
    MLSignalOutput,
    ModelCard,
    SignalDirection,
    FeatureImportance,
)

logger = logging.getLogger("365advisers.ml_signals.predictor")


class MLPredictor:
    """
    Generate ML signals using a trained model.

    Provides calibrated probability output, confidence scoring,
    and directional classification based on configurable thresholds.
    """

    BULLISH_THRESHOLD = 0.60
    BEARISH_THRESHOLD = 0.40

    @classmethod
    def predict(
        cls,
        model: object,
        feature_vector: dict[str, float],
        model_card: ModelCard,
        *,
        bullish_threshold: float = BULLISH_THRESHOLD,
        bearish_threshold: float = BEARISH_THRESHOLD,
        top_n_features: int = 5,
    ) -> MLSignalOutput:
        """
        Generate an ML signal for a single ticker.

        Args:
            model: Fitted sklearn model.
            feature_vector: Dict of feature_name → value.
            model_card: Model metadata for context.
            bullish_threshold: Probability above which signal is BULLISH.
            bearish_threshold: Probability below which signal is BEARISH.
            top_n_features: Number of top features to include.

        Returns:
            MLSignalOutput with prediction, confidence, and direction.
        """
        # Align feature vector to model's expected features
        feature_names = model_card.feature_names or list(feature_vector.keys())
        X = np.array(
            [[feature_vector.get(f, 0.0) for f in feature_names]],
            dtype=np.float64,
        )
        X = np.nan_to_num(X, nan=0.0)

        # Predict
        raw_prediction = 0.5
        try:
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(X)
                raw_prediction = float(probs[0, 1]) if probs.shape[1] == 2 else float(probs[0, 0])
            else:
                pred = model.predict(X)
                raw_prediction = float(pred[0])
        except Exception as e:
            logger.error("Prediction failed: %s", e)

        # Direction
        direction = cls._classify_direction(
            raw_prediction, bullish_threshold, bearish_threshold
        )

        # Confidence: distance from neutral center (0.5)
        confidence = cls._compute_confidence(raw_prediction)

        # Top feature contributions
        top_features = cls._get_top_features(
            model_card.feature_importances, top_n_features
        )

        ticker = feature_vector.get("_ticker", "UNKNOWN")

        return MLSignalOutput(
            ticker=ticker,
            prediction=round(raw_prediction, 4),
            confidence=round(confidence, 4),
            direction=direction,
            model_id=model_card.model_id,
            model_type=model_card.model_type.value,
            top_features=top_features,
        )

    @staticmethod
    def _classify_direction(
        probability: float,
        bullish_threshold: float,
        bearish_threshold: float,
    ) -> SignalDirection:
        """Map probability to directional signal."""
        if probability >= bullish_threshold:
            return SignalDirection.BULLISH
        elif probability <= bearish_threshold:
            return SignalDirection.BEARISH
        return SignalDirection.NEUTRAL

    @staticmethod
    def _compute_confidence(probability: float) -> float:
        """
        Compute confidence score from raw probability.

        Confidence = 2 × |prob - 0.5|  →  ranges from 0 (uncertain) to 1 (certain)
        """
        return min(1.0, 2.0 * abs(probability - 0.5))

    @staticmethod
    def _get_top_features(
        importances: list[FeatureImportance],
        top_n: int,
    ) -> list[FeatureImportance]:
        """Return top-N features by importance."""
        sorted_imp = sorted(importances, key=lambda f: f.importance, reverse=True)
        return sorted_imp[:top_n]
