"""
src/engines/dl_signals/transformer.py — Transformer-based signal model.

Lightweight numpy implementation of self-attention for financial time series.
For production, replace with PyTorch nn.Transformer.
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.dl_signals.models import DLSignalConfig, DLPrediction, DLModelInfo, DLModelType

logger = logging.getLogger("365advisers.dl_signals.transformer")


class TransformerSignalModel:
    """
    Transformer signal generator with self-attention.

    Architecture: Input → Self-Attention → FFN → Output
    """

    def __init__(self, config: DLSignalConfig | None = None):
        self.config = config or DLSignalConfig(model_type=DLModelType.TRANSFORMER)
        self._trained = False
        self._weights: dict = {}
        self._train_loss = 0.0
        self._directional_acc = 0.0

    def train(self, features: np.ndarray, targets: np.ndarray) -> DLModelInfo:
        """
        Train transformer on feature sequences.

        features: [n_samples × lookback × n_features]
        targets: [n_samples]
        """
        n_samples, lookback, n_features = features.shape
        d_model = self.config.hidden_size

        # Initialise weights
        scale = 1.0 / np.sqrt(d_model)
        self._weights = {
            "W_embed": np.random.randn(n_features, d_model) * scale,
            "W_q": np.random.randn(d_model, d_model) * scale,
            "W_k": np.random.randn(d_model, d_model) * scale,
            "W_v": np.random.randn(d_model, d_model) * scale,
            "W_ff1": np.random.randn(d_model, d_model * 2) * scale,
            "W_ff2": np.random.randn(d_model * 2, d_model) * scale,
            "W_out": np.random.randn(d_model, 1) * scale,
            "b_out": np.zeros(1),
        }

        # Positional encoding
        pe = np.zeros((lookback, d_model))
        pos = np.arange(lookback)[:, None]
        div = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))
        pe[:, 0::2] = np.sin(pos * div[:d_model//2])
        pe[:, 1::2] = np.cos(pos * div[:d_model//2])
        self._weights["pe"] = pe

        # Training
        best_loss = float("inf")
        for epoch in range(self.config.epochs):
            preds = np.array([self._forward(features[i]) for i in range(n_samples)])
            loss = float(np.mean((preds - targets) ** 2))

            if loss < best_loss:
                best_loss = loss

            # Evolutionary perturbation on output weights
            if epoch % 5 == 0:
                for key in ["W_out", "b_out"]:
                    noise = np.random.randn(*self._weights[key].shape) * 0.01
                    self._weights[key] += noise
                    new_preds = np.array([self._forward(features[i]) for i in range(n_samples)])
                    new_loss = float(np.mean((new_preds - targets) ** 2))
                    if new_loss >= loss:
                        self._weights[key] -= noise

        final_preds = np.array([self._forward(features[i]) for i in range(n_samples)])
        self._train_loss = float(np.mean((final_preds - targets) ** 2))
        correct = np.sum(np.sign(final_preds) == np.sign(targets))
        self._directional_acc = float(correct / len(targets))
        self._trained = True

        n_params = sum(w.size for w in self._weights.values())
        return DLModelInfo(
            model_type=DLModelType.TRANSFORMER,
            architecture=f"Transformer(d={d_model}, heads=1, ff={d_model*2})",
            total_params=n_params,
            training_loss=round(self._train_loss, 8),
            directional_accuracy=round(self._directional_acc, 4),
            lookback=self.config.lookback,
            horizon=self.config.horizon,
        )

    def predict(self, features: np.ndarray, ticker: str = "") -> DLPrediction:
        pred = self._forward(features)
        signal = float(np.tanh(pred * 10))
        confidence = min(abs(signal), 1.0)

        return DLPrediction(
            ticker=ticker, model_type="transformer",
            signal=round(signal, 4),
            predicted_return=round(float(pred), 6),
            confidence=round(confidence, 4),
            horizon=self.config.horizon,
            features_used=self.config.features,
        )

    def _forward(self, x: np.ndarray) -> float:
        """Forward: embed → self-attention → FFN → pooling → output."""
        # Embed + positional encoding
        h = x @ self._weights["W_embed"] + self._weights["pe"][:x.shape[0]]

        # Self-attention: Q, K, V
        Q = h @ self._weights["W_q"]
        K = h @ self._weights["W_k"]
        V = h @ self._weights["W_v"]

        d_k = Q.shape[-1]
        scores = Q @ K.T / np.sqrt(d_k)
        attn = self._softmax(scores)
        context = attn @ V

        # Residual connection
        h = h + context

        # FFN
        ff = np.maximum(0, h @ self._weights["W_ff1"])  # ReLU
        ff = ff @ self._weights["W_ff2"]
        h = h + ff

        # Global average pooling → output
        pooled = np.mean(h, axis=0)
        y = pooled @ self._weights["W_out"] + self._weights["b_out"]
        return float(y[0])

    @staticmethod
    def _softmax(x):
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)
