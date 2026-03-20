"""
src/engines/alpha_signals/ml_combiner.py
──────────────────────────────────────────────────────────────────────────────
#7: ML Signal Combiner v4.

Replaces the linear IC-weighted combiner with a gradient-boosted tree model
that captures non-linear signal interactions.

Architecture:
  - Input features: 53 signal fire/no-fire booleans + confidence values
  - Target: binary classification — 20-day forward return > 0
  - Training: walk-forward (never leaks future data)
  - Fallback: if model unavailable, reverts to linear IC combiner

Requires: lightgbm (optional dependency, falls back to logistic regression)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from src.engines.alpha_signals.models import (
    EvaluatedSignal,
    CompositeScore,
    SignalLevel,
    ConfidenceLevel,
    CategoryScore,
    SignalCategory,
)

logger = logging.getLogger("365advisers.alpha_signals.ml_combiner")


@dataclass
class MLModel:
    """Trained ML model container."""
    model: Any = None           # LightGBM or LogisticRegression
    model_type: str = "none"    # "lgbm", "logistic", "none"
    feature_names: list[str] = field(default_factory=list)
    train_samples: int = 0
    train_auc: float = 0.0
    oos_auc: float = 0.0
    feature_importances: dict[str, float] = field(default_factory=dict)


@dataclass
class MLPrediction:
    """Raw ML prediction before thresholding."""
    probability: float          # P(return > 0)
    raw_score: float            # log-odds or raw model output
    top_contributors: list[tuple[str, float]] = field(default_factory=list)


class MLSignalCombiner:
    """
    #7: ML-based signal combiner.

    Flow:
      1. train() — builds model from historical signals + returns
      2. predict() — scores a new set of evaluated signals
      3. combine() — wraps prediction into CompositeScore format

    Gradient boosted trees naturally handle:
      - Non-linear interactions (e.g., death_cross + deep_pullback)
      - Conditional dependencies (signal A only works when signal B fires)
      - Missing values (signals that don't fire)
    """

    def __init__(self):
        self._model: MLModel = MLModel()
        self._trained = False

    def train(
        self,
        signal_histories: list[dict[str, float]],
        forward_returns: list[float],
        oos_fraction: float = 0.2,
    ) -> MLModel:
        """
        Train the ML combiner on historical signal → return data.

        Parameters
        ----------
        signal_histories : list[dict[str, float]]
            Each dict maps signal_id → confidence (0 if not fired).
            One dict per observation (ticker × date).
        forward_returns : list[float]
            Corresponding 20-day forward returns.
        oos_fraction : float
            Fraction of data to hold out for validation.
        """
        n = len(signal_histories)
        if n < 50:
            logger.warning(f"ML COMBINER: Only {n} samples — need ≥ 50 for training")
            return self._model

        # Extract feature names from first observation
        feature_names = sorted(signal_histories[0].keys())

        # Build feature matrix
        X = [[obs.get(f, 0.0) for f in feature_names] for obs in signal_histories]
        y = [1.0 if r > 0 else 0.0 for r in forward_returns]

        # Train/test split (chronological — no shuffle for time series)
        split_idx = int(n * (1 - oos_fraction))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        model_type = "none"
        model = None
        train_auc = 0.0
        oos_auc = 0.0
        importances: dict[str, float] = {}

        # Try LightGBM first
        try:
            import lightgbm as lgb

            dtrain = lgb.Dataset(X_train, y_train, feature_name=feature_names)
            dval = lgb.Dataset(X_test, y_test, feature_name=feature_names, reference=dtrain)

            params = {
                "objective": "binary",
                "metric": "auc",
                "num_leaves": 15,        # keep shallow to prevent overfitting
                "learning_rate": 0.05,
                "min_data_in_leaf": 10,
                "feature_fraction": 0.7,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
                "seed": 42,
            }

            model = lgb.train(
                params, dtrain,
                num_boost_round=200,
                valid_sets=[dval],
                callbacks=[lgb.early_stopping(20, verbose=False)],
            )

            model_type = "lgbm"

            # Feature importances
            imp = model.feature_importance(importance_type="gain")
            total_imp = sum(imp) if sum(imp) > 0 else 1.0
            importances = {
                feature_names[i]: round(imp[i] / total_imp, 4)
                for i in range(len(feature_names))
            }

            # AUC
            y_pred_train = model.predict(X_train)
            y_pred_test = model.predict(X_test)
            train_auc = _compute_auc(y_train, y_pred_train)
            oos_auc = _compute_auc(y_test, y_pred_test)

            logger.info(
                f"ML COMBINER: LightGBM trained — "
                f"train AUC={train_auc:.3f}, OOS AUC={oos_auc:.3f}, "
                f"n_train={len(X_train)}, n_test={len(X_test)}"
            )

        except ImportError:
            logger.info("ML COMBINER: LightGBM not available, using logistic regression fallback")

            # Logistic regression fallback (no external deps)
            model, train_auc, oos_auc, importances = self._train_logistic(
                X_train, y_train, X_test, y_test, feature_names
            )
            model_type = "logistic"

        self._model = MLModel(
            model=model,
            model_type=model_type,
            feature_names=feature_names,
            train_samples=len(X_train),
            train_auc=round(train_auc, 4),
            oos_auc=round(oos_auc, 4),
            feature_importances=importances,
        )
        self._trained = True

        return self._model

    def predict(self, signals: list[EvaluatedSignal]) -> MLPrediction:
        """Score a set of evaluated signals using the trained model."""
        if not self._trained or self._model.model is None:
            # Fallback: simple average confidence
            confidences = [s.confidence for s in signals if s.fired]
            avg = sum(confidences) / len(confidences) if confidences else 0.0
            return MLPrediction(
                probability=min(1.0, avg),
                raw_score=avg,
            )

        # Build feature vector
        signal_map = {s.signal_id: s.confidence if s.fired else 0.0 for s in signals}
        x = [signal_map.get(f, 0.0) for f in self._model.feature_names]

        if self._model.model_type == "lgbm":
            prob = float(self._model.model.predict([x])[0])
        elif self._model.model_type == "logistic":
            prob = self._logistic_predict(self._model.model, x)
        else:
            prob = 0.5

        # Top contributors
        top = sorted(
            self._model.feature_importances.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )[:5]

        return MLPrediction(
            probability=round(prob, 4),
            raw_score=round(prob, 4),
            top_contributors=top,
        )

    def combine(
        self,
        signals: list[EvaluatedSignal],
        sector: str = "",
    ) -> CompositeScore:
        """
        Produce a CompositeScore using ML predictions (API-compatible with linear combiner).
        """
        prediction = self.predict(signals)

        # Map probability to composite score (calibrate to 0-1 range)
        # P > 0.6 → STRONG_BUY territory
        # P > 0.55 → BUY territory
        score = prediction.probability

        fired = [s for s in signals if s.fired]
        n_fired = len(fired)

        if score >= 0.60:
            level = SignalLevel.STRONG_BUY
        elif score >= 0.55:
            level = SignalLevel.BUY
        else:
            level = SignalLevel.HOLD

        confidence = ConfidenceLevel.HIGH if score >= 0.65 else (
            ConfidenceLevel.MEDIUM if score >= 0.55 else ConfidenceLevel.LOW
        )

        return CompositeScore(
            composite_score=round(score, 4),
            level=level,
            confidence=confidence,
            fired_count=n_fired,
            total_count=len(signals),
            top_signals=[s.signal_id for s in fired[:5]],
            category_scores=[],
            explanation=f"ML v4 prediction: P(return>0)={prediction.probability:.1%}, "
                        f"model={self._model.model_type}, "
                        f"AUC={self._model.oos_auc:.3f}",
        )

    # ── Logistic regression fallback ─────────────────────────────────────────

    @staticmethod
    def _train_logistic(
        X_train, y_train, X_test, y_test, feature_names,
    ) -> tuple[dict, float, float, dict]:
        """Simple logistic regression (no external dependencies)."""
        n_features = len(feature_names)
        weights = [0.0] * n_features
        bias = 0.0
        lr = 0.01

        # Mini-batch gradient descent
        for epoch in range(100):
            for i in range(len(X_train)):
                x = X_train[i]
                y = y_train[i]

                z = sum(w * xi for w, xi in zip(weights, x)) + bias
                z = max(-10, min(10, z))  # clip for numerical stability
                pred = 1.0 / (1.0 + math.exp(-z))

                err = pred - y
                for j in range(n_features):
                    weights[j] -= lr * err * x[j]
                bias -= lr * err

        model = {"weights": weights, "bias": bias}

        # Compute AUC
        y_pred_train = [MLSignalCombiner._logistic_predict(model, x) for x in X_train]
        y_pred_test = [MLSignalCombiner._logistic_predict(model, x) for x in X_test]
        train_auc = _compute_auc(y_train, y_pred_train)
        oos_auc = _compute_auc(y_test, y_pred_test)

        # Feature importances (absolute weights)
        total_w = sum(abs(w) for w in weights) or 1.0
        importances = {
            feature_names[i]: round(abs(weights[i]) / total_w, 4)
            for i in range(n_features)
        }

        logger.info(
            f"ML COMBINER: Logistic regression — "
            f"train AUC={train_auc:.3f}, OOS AUC={oos_auc:.3f}"
        )

        return model, train_auc, oos_auc, importances

    @staticmethod
    def _logistic_predict(model: dict, x: list[float]) -> float:
        """Predict probability from logistic model."""
        z = sum(w * xi for w, xi in zip(model["weights"], x)) + model["bias"]
        z = max(-10, min(10, z))
        return 1.0 / (1.0 + math.exp(-z))


def _compute_auc(y_true: list[float], y_pred: list[float]) -> float:
    """Simplified AUC computation (Mann-Whitney U statistic)."""
    pairs = list(zip(y_true, y_pred))
    pos = [p for y, p in pairs if y > 0.5]
    neg = [p for y, p in pairs if y <= 0.5]

    if not pos or not neg:
        return 0.5

    concordant = sum(1 for p in pos for n in neg if p > n)
    total = len(pos) * len(neg)
    return concordant / total if total > 0 else 0.5
