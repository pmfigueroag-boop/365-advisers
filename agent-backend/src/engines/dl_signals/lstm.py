"""
src/engines/dl_signals/lstm.py — LSTM-based signal model.

Uses numpy for a lightweight LSTM implementation that works without PyTorch/TF.
For production, replace the forward pass with a proper PyTorch LSTM.
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.dl_signals.models import DLSignalConfig, DLPrediction, DLModelInfo, DLModelType

logger = logging.getLogger("365advisers.dl_signals.lstm")


class LSTMSignalModel:
    """
    LSTM signal generator.

    Lightweight numpy implementation for inference:
    - Input: [lookback × features] sequence
    - Hidden: configurable layers × hidden_size
    - Output: predicted return + signal strength
    """

    def __init__(self, config: DLSignalConfig | None = None):
        self.config = config or DLSignalConfig(model_type=DLModelType.LSTM)
        self._trained = False
        self._weights: dict = {}
        self._train_loss = 0.0
        self._val_loss = 0.0
        self._directional_acc = 0.0

    def train(self, features: np.ndarray, targets: np.ndarray) -> DLModelInfo:
        """
        Train LSTM on feature sequences.

        Args:
            features: [n_samples × lookback × n_features]
            targets: [n_samples] next-period returns
        """
        n_samples, lookback, n_features = features.shape
        hs = self.config.hidden_size

        # Initialise weights (Xavier)
        scale = 1.0 / np.sqrt(n_features + hs)
        self._weights = {
            "Wf": np.random.randn(n_features + hs, hs) * scale,
            "Wi": np.random.randn(n_features + hs, hs) * scale,
            "Wc": np.random.randn(n_features + hs, hs) * scale,
            "Wo": np.random.randn(n_features + hs, hs) * scale,
            "Wy": np.random.randn(hs, 1) * scale,
            "bf": np.zeros(hs), "bi": np.zeros(hs),
            "bc": np.zeros(hs), "bo": np.zeros(hs),
            "by": np.zeros(1),
        }

        # Simplified training (gradient-free: use correlation-based weight update)
        best_loss = float("inf")
        for epoch in range(self.config.epochs):
            preds = np.array([self._forward(features[i]) for i in range(n_samples)])
            loss = float(np.mean((preds - targets) ** 2))

            if loss < best_loss:
                best_loss = loss

            # Stochastic perturbation (evolutionary strategy)
            if epoch % 5 == 0:
                for key in ["Wy", "by"]:
                    noise = np.random.randn(*self._weights[key].shape) * 0.01
                    self._weights[key] += noise
                    new_preds = np.array([self._forward(features[i]) for i in range(n_samples)])
                    new_loss = float(np.mean((new_preds - targets) ** 2))
                    if new_loss >= loss:
                        self._weights[key] -= noise

        # Final predictions
        final_preds = np.array([self._forward(features[i]) for i in range(n_samples)])
        self._train_loss = float(np.mean((final_preds - targets) ** 2))

        # Directional accuracy
        correct = np.sum(np.sign(final_preds) == np.sign(targets))
        self._directional_acc = float(correct / len(targets))

        self._trained = True

        n_params = sum(w.size for w in self._weights.values())
        return DLModelInfo(
            model_type=DLModelType.LSTM,
            architecture=f"LSTM({n_features}→{hs}×{self.config.num_layers}→1)",
            total_params=n_params,
            training_loss=round(self._train_loss, 8),
            directional_accuracy=round(self._directional_acc, 4),
            lookback=self.config.lookback,
            horizon=self.config.horizon,
        )

    def predict(self, features: np.ndarray, ticker: str = "") -> DLPrediction:
        """Predict return from feature sequence [lookback × n_features]."""
        pred = self._forward(features)
        signal = float(np.tanh(pred * 10))  # scale to [-1, 1]
        confidence = min(abs(signal), 1.0)

        return DLPrediction(
            ticker=ticker, model_type="lstm",
            signal=round(signal, 4),
            predicted_return=round(float(pred), 6),
            confidence=round(confidence, 4),
            horizon=self.config.horizon,
            features_used=self.config.features,
        )

    def _forward(self, x: np.ndarray) -> float:
        """Forward pass through LSTM cell."""
        lookback = x.shape[0]
        hs = self.config.hidden_size

        h = np.zeros(hs)
        c = np.zeros(hs)

        for t in range(lookback):
            xt = x[t]
            combined = np.concatenate([xt, h])

            f = self._sigmoid(combined @ self._weights["Wf"] + self._weights["bf"])
            i = self._sigmoid(combined @ self._weights["Wi"] + self._weights["bi"])
            c_hat = np.tanh(combined @ self._weights["Wc"] + self._weights["bc"])
            o = self._sigmoid(combined @ self._weights["Wo"] + self._weights["bo"])

            c = f * c + i * c_hat
            h = o * np.tanh(c)

        y = h @ self._weights["Wy"] + self._weights["by"]
        return float(y[0])

    @staticmethod
    def _sigmoid(x):
        return 1 / (1 + np.exp(-np.clip(x, -20, 20)))
