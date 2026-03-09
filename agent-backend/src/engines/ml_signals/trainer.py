"""
src/engines/ml_signals/trainer.py
──────────────────────────────────────────────────────────────────────────────
ML model training pipeline.

Supports RandomForest, GradientBoosting, Logistic, Linear, and Lasso
models from sklearn. Uses walk-forward train/test split to prevent
temporal leakage.
"""

from __future__ import annotations

import base64
import logging
import pickle
from uuid import uuid4

import numpy as np

from src.engines.ml_signals.models import (
    MLModelConfig,
    ModelCard,
    ModelStatus,
    ModelType,
    FeatureImportance,
)

logger = logging.getLogger("365advisers.ml_signals.trainer")


class MLTrainer:
    """
    Train sklearn models for alpha signal generation.

    Walk-forward split: the last `test_size` fraction of data is held out
    (respecting temporal order — no future leakage).
    """

    @classmethod
    def train(
        cls,
        features: np.ndarray | list[list[float]],
        target: np.ndarray | list[float],
        feature_names: list[str] | None = None,
        config: MLModelConfig | None = None,
    ) -> tuple[ModelCard, object]:
        """
        Train a model and return (ModelCard, fitted_model).

        Args:
            features: 2D array of shape (n_samples, n_features).
            target: 1D array of shape (n_samples,) — raw returns or binary labels.
            feature_names: Optional list of feature names.
            config: Training configuration.

        Returns:
            Tuple of (ModelCard with metrics, fitted sklearn model).
        """
        config = config or MLModelConfig()
        X = np.asarray(features, dtype=np.float64)
        y = np.asarray(target, dtype=np.float64)

        if len(X.shape) != 2:
            raise ValueError(f"Features must be 2D, got shape {X.shape}")
        n_samples, n_features = X.shape

        # Feature names
        if feature_names is None:
            feature_names = [f"f_{i}" for i in range(n_features)]

        # Walk-forward split (temporal: train on earlier, test on later)
        split_idx = int(n_samples * (1 - config.test_size))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Binary classification: convert returns to labels
        y_train_cls = (y_train > config.class_threshold).astype(int)
        y_test_cls = (y_test > config.class_threshold).astype(int)

        # Build model
        model = cls._build_model(config)

        # Handle NaN
        X_train = np.nan_to_num(X_train, nan=0.0)
        X_test = np.nan_to_num(X_test, nan=0.0)

        try:
            model.fit(X_train, y_train_cls)
            status = ModelStatus.READY
        except Exception as e:
            logger.error("Training failed: %s", e)
            return ModelCard(
                model_id=uuid4().hex[:12],
                model_type=config.model_type,
                status=ModelStatus.FAILED,
                config=config,
            ), None

        # Evaluate
        y_pred = model.predict(X_test)
        y_prob = cls._safe_predict_proba(model, X_test)

        metrics = cls._compute_metrics(y_test_cls, y_pred, y_prob, y_test)

        # Feature importances
        importances = cls._extract_importances(model, feature_names)

        model_id = uuid4().hex[:12]

        card = ModelCard(
            model_id=model_id,
            model_type=config.model_type,
            status=status,
            training_samples=len(X_train),
            test_samples=len(X_test),
            feature_count=n_features,
            feature_names=feature_names,
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1_score=metrics["f1_score"],
            information_coefficient=metrics["ic"],
            hit_rate=metrics["hit_rate"],
            feature_importances=importances,
            config=config,
        )

        logger.info(
            "Model %s trained: acc=%.3f, prec=%.3f, IC=%.3f, features=%d, samples=%d",
            model_id, card.accuracy, card.precision, card.information_coefficient,
            n_features, n_samples,
        )

        return card, model

    @classmethod
    def serialize_model(cls, model: object) -> str:
        """Serialize a sklearn model to base64 string."""
        return base64.b64encode(pickle.dumps(model)).decode("utf-8")

    @classmethod
    def deserialize_model(cls, model_b64: str) -> object:
        """Deserialize a sklearn model from base64 string."""
        return pickle.loads(base64.b64decode(model_b64))

    # ── Internal ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_model(config: MLModelConfig):
        """Instantiate the appropriate sklearn model."""
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression, SGDClassifier

        if config.model_type == ModelType.RANDOM_FOREST:
            return RandomForestClassifier(
                n_estimators=config.n_estimators,
                max_depth=config.max_depth,
                min_samples_leaf=config.min_samples_leaf,
                random_state=config.random_state,
                n_jobs=-1,
            )
        elif config.model_type == ModelType.GRADIENT_BOOST:
            return GradientBoostingClassifier(
                n_estimators=config.n_estimators,
                max_depth=min(config.max_depth or 5, 10),
                learning_rate=config.learning_rate,
                min_samples_leaf=config.min_samples_leaf,
                random_state=config.random_state,
            )
        elif config.model_type == ModelType.LOGISTIC:
            return LogisticRegression(
                max_iter=1000,
                random_state=config.random_state,
            )
        elif config.model_type in (ModelType.LINEAR, ModelType.LASSO):
            return SGDClassifier(
                loss="log_loss",
                penalty="l1" if config.model_type == ModelType.LASSO else "l2",
                max_iter=1000,
                random_state=config.random_state,
            )
        else:
            raise ValueError(f"Unsupported model type: {config.model_type}")

    @staticmethod
    def _safe_predict_proba(model, X: np.ndarray) -> np.ndarray | None:
        """Get probability predictions if available."""
        if hasattr(model, "predict_proba"):
            try:
                probs = model.predict_proba(X)
                return probs[:, 1] if probs.shape[1] == 2 else probs[:, 0]
            except Exception:
                return None
        return None

    @staticmethod
    def _compute_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_prob: np.ndarray | None,
        y_returns: np.ndarray,
    ) -> dict[str, float]:
        """Compute classification and alpha-relevant metrics."""
        n = len(y_true)
        if n == 0:
            return {"accuracy": 0, "precision": 0, "recall": 0, "f1_score": 0, "ic": 0, "hit_rate": 0}

        # Accuracy
        accuracy = float(np.mean(y_true == y_pred))

        # Precision, Recall, F1 (binary)
        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        fp = int(np.sum((y_pred == 1) & (y_true == 0)))
        fn = int(np.sum((y_pred == 0) & (y_true == 1)))

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-10)

        # Information Coefficient (rank correlation between prob and actual return)
        ic = 0.0
        if y_prob is not None and len(y_prob) > 2:
            from scipy.stats import spearmanr
            try:
                ic, _ = spearmanr(y_prob, y_returns)
                if not np.isfinite(ic):
                    ic = 0.0
            except Exception:
                ic = 0.0

        # Hit rate: fraction of bullish predictions that were correct
        bullish_mask = y_pred == 1
        hit_rate = float(np.mean(y_true[bullish_mask] == 1)) if bullish_mask.sum() > 0 else 0.0

        return {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "ic": round(float(ic), 4),
            "hit_rate": round(hit_rate, 4),
        }

    @staticmethod
    def _extract_importances(
        model,
        feature_names: list[str],
    ) -> list[FeatureImportance]:
        """Extract feature importances from a fitted model."""
        importances_raw = None

        if hasattr(model, "feature_importances_"):
            importances_raw = model.feature_importances_
        elif hasattr(model, "coef_"):
            importances_raw = np.abs(model.coef_.flatten())

        if importances_raw is None:
            return []

        # Normalise
        total = importances_raw.sum()
        if total > 0:
            importances_raw = importances_raw / total

        # Build sorted list
        pairs = list(zip(feature_names, importances_raw))
        pairs.sort(key=lambda x: x[1], reverse=True)

        return [
            FeatureImportance(
                feature_name=name,
                importance=round(float(imp), 6),
                rank=i + 1,
            )
            for i, (name, imp) in enumerate(pairs)
        ]
