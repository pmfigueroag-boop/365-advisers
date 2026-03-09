"""
tests/test_dl_signals.py — Deep learning signal tests.
"""
import numpy as np
import pytest
from src.engines.dl_signals.models import DLModelType, DLSignalConfig
from src.engines.dl_signals.lstm import LSTMSignalModel
from src.engines.dl_signals.transformer import TransformerSignalModel
from src.engines.dl_signals.engine import DLSignalEngine


def _sample_data(n=300, lookback=30, n_features=4):
    np.random.seed(42)
    features = np.random.randn(n, lookback, n_features) * 0.01
    targets = np.random.randn(n) * 0.01
    return features, targets


def _sample_prices(n=200):
    np.random.seed(42)
    return (175 * np.cumprod(1 + np.random.randn(n) * 0.01)).tolist()


class TestLSTM:
    def test_train(self):
        config = DLSignalConfig(model_type=DLModelType.LSTM, hidden_size=16, epochs=5, lookback=30)
        model = LSTMSignalModel(config)
        features, targets = _sample_data(50, 30, 4)
        info = model.train(features, targets)
        assert info.model_type == DLModelType.LSTM
        assert info.total_params > 0

    def test_predict(self):
        config = DLSignalConfig(hidden_size=16, epochs=5, lookback=30)
        model = LSTMSignalModel(config)
        features, targets = _sample_data(50, 30, 4)
        model.train(features, targets)
        pred = model.predict(features[-1], "AAPL")
        assert pred.ticker == "AAPL"
        assert -1.0 <= pred.signal <= 1.0

    def test_signal_range(self):
        config = DLSignalConfig(hidden_size=16, epochs=3, lookback=30)
        model = LSTMSignalModel(config)
        features, targets = _sample_data(50, 30, 4)
        model.train(features, targets)
        for i in range(10):
            pred = model.predict(features[i], "TEST")
            assert -1.0 <= pred.signal <= 1.0
            assert 0 <= pred.confidence <= 1.0


class TestTransformer:
    def test_train(self):
        config = DLSignalConfig(model_type=DLModelType.TRANSFORMER, hidden_size=16, epochs=5, lookback=30)
        model = TransformerSignalModel(config)
        features, targets = _sample_data(50, 30, 4)
        info = model.train(features, targets)
        assert info.model_type == DLModelType.TRANSFORMER
        assert "Transformer" in info.architecture

    def test_predict(self):
        config = DLSignalConfig(model_type=DLModelType.TRANSFORMER, hidden_size=16, epochs=5, lookback=30)
        model = TransformerSignalModel(config)
        features, targets = _sample_data(50, 30, 4)
        model.train(features, targets)
        pred = model.predict(features[-1], "MSFT")
        assert pred.model_type == "transformer"
        assert -1.0 <= pred.signal <= 1.0


class TestDLEngine:
    def test_prepare_features(self):
        prices = _sample_prices(200)
        features, targets = DLSignalEngine.prepare_features(prices, lookback=30)
        assert features.shape[1] == 30
        assert features.shape[2] == 4
        assert len(targets) == len(features)

    def test_train_and_predict(self):
        prices = {"AAPL": _sample_prices(200)}
        config = DLSignalConfig(lookback=30, hidden_size=16, epochs=3)
        preds = DLSignalEngine.train_and_predict(prices, config)
        assert "AAPL" in preds
        assert -1.0 <= preds["AAPL"].signal <= 1.0

    def test_insufficient_data(self):
        prices = {"SHORT": [100, 101, 102]}
        config = DLSignalConfig(lookback=60)
        preds = DLSignalEngine.train_and_predict(prices, config)
        assert "SHORT" not in preds  # skipped

    def test_ensemble(self):
        prices = {"AAPL": _sample_prices(200)}
        config = DLSignalConfig(lookback=30, hidden_size=16, epochs=3)
        preds = DLSignalEngine.generate_ensemble(prices, config)
        assert "AAPL" in preds
        assert preds["AAPL"].model_type == "ensemble"
