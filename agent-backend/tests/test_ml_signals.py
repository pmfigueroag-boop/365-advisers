"""
tests/test_ml_signals.py
──────────────────────────────────────────────────────────────────────────────
Tests for the ML Signal Factory.
"""

import numpy as np
import pytest

from src.engines.ml_signals.models import (
    ModelType,
    ModelStatus,
    SignalDirection,
    MLModelConfig,
    FeatureImportance,
    MLSignalOutput,
    ModelCard,
)
from src.engines.ml_signals.feature_engineering import build_feature_vector, normalise_features
from src.engines.ml_signals.trainer import MLTrainer
from src.engines.ml_signals.predictor import MLPredictor
from src.engines.ml_signals.model_registry import ModelRegistry
from src.engines.ml_signals.engine import MLSignalFactory
from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_synthetic_data(n_samples=200, n_features=10, seed=42):
    """Generate synthetic classification data."""
    np.random.seed(seed)
    X = np.random.randn(n_samples, n_features)
    # Target: forward return proportional to first 3 features + noise
    y = 0.3 * X[:, 0] + 0.2 * X[:, 1] - 0.1 * X[:, 2] + np.random.randn(n_samples) * 0.5
    return X, y


def _make_fundamental():
    return FundamentalFeatureSet(
        ticker="AAPL",
        roic=0.25, roe=0.40, gross_margin=0.43,
        ebit_margin=0.30, net_margin=0.25,
        fcf_yield=0.035, debt_to_equity=1.8,
        current_ratio=1.1, revenue_growth_yoy=0.08,
        earnings_growth_yoy=0.12, pe_ratio=28.5,
        pb_ratio=45.0, ev_ebitda=22.0,
        dividend_yield=0.006, beta=1.2,
        margin_trend=0.02, earnings_stability=0.85,
    )


def _make_technical():
    return TechnicalFeatureSet(
        ticker="AAPL",
        current_price=175.0, sma_50=170.0, sma_200=160.0,
        ema_20=172.0, rsi=58.0, stoch_k=65.0, stoch_d=60.0,
        macd=2.5, macd_signal=1.8, macd_hist=0.7,
        bb_upper=180.0, bb_lower=165.0, bb_basis=172.5,
        atr=3.2, volume=75e6, obv=1.2e9, volume_avg_20=70e6,
    )


# ── Feature Engineering Tests ────────────────────────────────────────────────

class TestFeatureEngineering:
    def test_build_vector_fundamental_only(self):
        fv = build_feature_vector(fundamental=_make_fundamental())
        assert "roic" in fv
        assert "pe_ratio" in fv
        assert fv["roic"] == 0.25
        assert len(fv) >= 15

    def test_build_vector_technical_only(self):
        fv = build_feature_vector(technical=_make_technical())
        assert "rsi" in fv
        assert "price_to_sma50" in fv
        assert len(fv) >= 10

    def test_build_vector_combined(self):
        fv = build_feature_vector(_make_fundamental(), _make_technical())
        assert "roic" in fv
        assert "rsi" in fv
        assert "value_momentum" in fv
        assert "quality_trend" in fv
        assert len(fv) >= 25

    def test_none_handling(self):
        fv = build_feature_vector(FundamentalFeatureSet(ticker="X"))
        assert fv["roic"] == 0.0

    def test_normalise_features(self):
        vectors = [
            {"a": 10, "b": 20},
            {"a": 20, "b": 40},
            {"a": 30, "b": 60},
        ]
        normed = normalise_features(vectors)
        assert len(normed) == 3
        # Z-score of middle element should be ~0
        assert abs(normed[1]["a"]) < 0.01


# ── Trainer Tests ────────────────────────────────────────────────────────────

class TestMLTrainer:
    def test_train_random_forest(self):
        X, y = _make_synthetic_data()
        config = MLModelConfig(model_type=ModelType.RANDOM_FOREST, n_estimators=50)
        card, model = MLTrainer.train(X, y, config=config)
        assert card.status == ModelStatus.READY
        assert card.accuracy > 0
        assert card.feature_count == 10
        assert len(card.feature_importances) > 0
        assert model is not None

    def test_train_gradient_boost(self):
        X, y = _make_synthetic_data()
        config = MLModelConfig(model_type=ModelType.GRADIENT_BOOST, n_estimators=30)
        card, model = MLTrainer.train(X, y, config=config)
        assert card.status == ModelStatus.READY
        assert card.accuracy > 0

    def test_train_logistic(self):
        X, y = _make_synthetic_data()
        config = MLModelConfig(model_type=ModelType.LOGISTIC)
        card, model = MLTrainer.train(X, y, config=config)
        assert card.status == ModelStatus.READY

    def test_feature_names_preserved(self):
        X, y = _make_synthetic_data(n_features=3)
        names = ["alpha", "beta", "gamma"]
        card, _ = MLTrainer.train(X, y, feature_names=names)
        assert card.feature_names == names
        assert card.feature_importances[0].feature_name in names

    def test_serialization_roundtrip(self):
        X, y = _make_synthetic_data()
        _, model = MLTrainer.train(X, y)
        b64 = MLTrainer.serialize_model(model)
        restored = MLTrainer.deserialize_model(b64)
        # Should produce same predictions
        pred_orig = model.predict(X[:5])
        pred_restored = restored.predict(X[:5])
        np.testing.assert_array_equal(pred_orig, pred_restored)


# ── Predictor Tests ──────────────────────────────────────────────────────────

class TestMLPredictor:
    def test_predict_output_structure(self):
        X, y = _make_synthetic_data()
        card, model = MLTrainer.train(X, y, feature_names=[f"f{i}" for i in range(10)])
        fv = {f"f{i}": 0.5 for i in range(10)}
        fv["_ticker"] = "AAPL"
        signal = MLPredictor.predict(model, fv, card)
        assert isinstance(signal, MLSignalOutput)
        assert signal.ticker == "AAPL"
        assert 0 <= signal.confidence <= 1
        assert signal.direction in SignalDirection

    def test_bullish_signal(self):
        d = MLPredictor._classify_direction(0.75, 0.6, 0.4)
        assert d == SignalDirection.BULLISH

    def test_bearish_signal(self):
        d = MLPredictor._classify_direction(0.25, 0.6, 0.4)
        assert d == SignalDirection.BEARISH

    def test_neutral_signal(self):
        d = MLPredictor._classify_direction(0.50, 0.6, 0.4)
        assert d == SignalDirection.NEUTRAL

    def test_confidence_extremes(self):
        assert MLPredictor._compute_confidence(1.0) == 1.0
        assert MLPredictor._compute_confidence(0.5) == 0.0
        assert MLPredictor._compute_confidence(0.0) == 1.0


# ── Registry Tests ───────────────────────────────────────────────────────────

class TestModelRegistry:
    def test_register_and_get(self):
        reg = ModelRegistry()
        card = ModelCard(model_id="m001", model_type=ModelType.RANDOM_FOREST)
        reg.register(card)
        assert reg.get_card("m001") is not None
        assert reg.total_models == 1

    def test_deploy_lifecycle(self):
        reg = ModelRegistry()
        card = ModelCard(model_id="m001", model_type=ModelType.RANDOM_FOREST, status=ModelStatus.READY)
        reg.register(card)
        assert reg.deploy("m001")
        assert reg.get_card("m001").status == ModelStatus.DEPLOYED

    def test_deploy_retires_previous(self):
        reg = ModelRegistry()
        c1 = ModelCard(model_id="m001", model_type=ModelType.RANDOM_FOREST, status=ModelStatus.READY)
        c2 = ModelCard(model_id="m002", model_type=ModelType.RANDOM_FOREST, status=ModelStatus.READY)
        reg.register(c1)
        reg.register(c2)
        reg.deploy("m001")
        reg.deploy("m002")
        assert reg.get_card("m001").status == ModelStatus.RETIRED
        assert reg.get_card("m002").status == ModelStatus.DEPLOYED

    def test_get_deployed(self):
        reg = ModelRegistry()
        card = ModelCard(model_id="m001", model_type=ModelType.GRADIENT_BOOST, status=ModelStatus.READY)
        reg.register(card)
        reg.deploy("m001")
        deployed = reg.get_deployed(ModelType.GRADIENT_BOOST)
        assert deployed is not None
        assert deployed.card.model_id == "m001"

    def test_compare_models(self):
        reg = ModelRegistry()
        c1 = ModelCard(model_id="a", f1_score=0.7)
        c2 = ModelCard(model_id="b", f1_score=0.8)
        reg.register(c1)
        reg.register(c2)
        result = reg.compare("a", "b")
        assert result["winner"] == "b"

    def test_retire(self):
        reg = ModelRegistry()
        card = ModelCard(model_id="m001", status=ModelStatus.DEPLOYED)
        reg.register(card)
        reg.retire("m001")
        assert reg.get_card("m001").status == ModelStatus.RETIRED


# ── Factory Integration Tests ────────────────────────────────────────────────

class TestMLSignalFactory:
    def test_train_and_predict(self):
        factory = MLSignalFactory()
        X, y = _make_synthetic_data()
        names = [f"f{i}" for i in range(10)]
        card = factory.train_model(X, y, feature_names=names)
        assert card.status == ModelStatus.READY

        # Deploy
        factory.deploy_model(card.model_id)

        # Predict
        fv = {f"f{i}": np.random.randn() for i in range(10)}
        signal = factory.generate_signal("AAPL", technical=None, fundamental=None)
        # With no features matching, should still return neutral
        assert signal.ticker == "AAPL"

    def test_no_deployed_model(self):
        factory = MLSignalFactory()
        signal = factory.generate_signal("AAPL")
        assert signal.direction == SignalDirection.NEUTRAL
        assert signal.confidence == 0.0
