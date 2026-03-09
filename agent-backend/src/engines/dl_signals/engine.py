"""
src/engines/dl_signals/engine.py — Deep Learning Signal Engine.
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.dl_signals.models import DLModelType, DLSignalConfig, DLPrediction, DLModelInfo
from src.engines.dl_signals.lstm import LSTMSignalModel
from src.engines.dl_signals.transformer import TransformerSignalModel

logger = logging.getLogger("365advisers.dl_signals.engine")


class DLSignalEngine:
    """Unified deep learning signal generation."""

    @classmethod
    def prepare_features(
        cls,
        prices: list[float],
        lookback: int = 60,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Prepare feature sequences from raw price series.

        Features: returns, volatility (20-day), momentum (10-day), volume_proxy
        Returns: features [n_samples × lookback × 4], targets [n_samples]
        """
        prices = np.array(prices)
        returns = np.diff(prices) / prices[:-1]
        n = len(returns)

        # Feature engineering
        vol_20 = np.array([np.std(returns[max(0, i-20):i]) if i >= 20 else np.std(returns[:i+1]) for i in range(n)])
        mom_10 = np.array([returns[i] - returns[max(0, i-10)] for i in range(n)])
        rsi_proxy = np.array([np.mean(returns[max(0, i-14):i] > 0) if i >= 14 else 0.5 for i in range(n)])

        all_features = np.column_stack([returns, vol_20, mom_10, rsi_proxy])

        # Create sequences
        features_list = []
        targets_list = []
        for i in range(lookback, n - 1):
            features_list.append(all_features[i - lookback:i])
            targets_list.append(returns[i])

        return np.array(features_list), np.array(targets_list)

    @classmethod
    def train_and_predict(
        cls,
        prices: dict[str, list[float]],
        config: DLSignalConfig | None = None,
    ) -> dict[str, DLPrediction]:
        """Train model on price data and generate signals for each ticker."""
        cfg = config or DLSignalConfig()

        # Create model
        if cfg.model_type == DLModelType.TRANSFORMER:
            model = TransformerSignalModel(cfg)
        else:
            model = LSTMSignalModel(cfg)

        predictions = {}
        for ticker, price_series in prices.items():
            if len(price_series) < cfg.lookback + 10:
                logger.warning("Insufficient data for %s (%d < %d)", ticker, len(price_series), cfg.lookback + 10)
                continue

            features, targets = cls.prepare_features(price_series, cfg.lookback)
            if len(features) < 10:
                continue

            # Train
            model.train(features, targets)

            # Predict using last sequence
            last_seq = features[-1]
            pred = model.predict(last_seq, ticker)
            predictions[ticker] = pred

        return predictions

    @classmethod
    def generate_ensemble(
        cls,
        prices: dict[str, list[float]],
        config: DLSignalConfig | None = None,
    ) -> dict[str, DLPrediction]:
        """Generate ensemble signal from LSTM + Transformer."""
        cfg = config or DLSignalConfig()

        # LSTM predictions
        lstm_cfg = DLSignalConfig(**cfg.model_dump() | {"model_type": DLModelType.LSTM})
        lstm_preds = cls.train_and_predict(prices, lstm_cfg)

        # Transformer predictions
        tf_cfg = DLSignalConfig(**cfg.model_dump() | {"model_type": DLModelType.TRANSFORMER})
        tf_preds = cls.train_and_predict(prices, tf_cfg)

        # Ensemble: weighted average (LSTM 0.5, Transformer 0.5)
        ensemble = {}
        for ticker in set(lstm_preds.keys()) | set(tf_preds.keys()):
            l = lstm_preds.get(ticker)
            t = tf_preds.get(ticker)

            if l and t:
                signal = (l.signal + t.signal) / 2
                conf = (l.confidence + t.confidence) / 2
                pred_ret = (l.predicted_return + t.predicted_return) / 2
            elif l:
                signal, conf, pred_ret = l.signal, l.confidence, l.predicted_return
            else:
                signal, conf, pred_ret = t.signal, t.confidence, t.predicted_return

            ensemble[ticker] = DLPrediction(
                ticker=ticker, model_type="ensemble",
                signal=round(signal, 4),
                predicted_return=round(pred_ret, 6),
                confidence=round(conf, 4),
                horizon=cfg.horizon,
                features_used=cfg.features,
            )

        return ensemble
