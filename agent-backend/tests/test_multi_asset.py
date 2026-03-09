"""tests/test_multi_asset.py — Multi-Asset Data Layer tests."""
import numpy as np
import pytest
from src.engines.multi_asset.models import AssetClass, AssetProfile, CorrelationMatrix
from src.engines.multi_asset.normaliser import ReturnNormaliser
from src.engines.multi_asset.correlation import CorrelationEngine
from src.engines.multi_asset.engine import MultiAssetEngine

class TestReturnNormaliser:
    def test_simple_returns(self):
        prices = [100, 105, 110, 108]
        ret = ReturnNormaliser.simple_returns(prices)
        assert len(ret) == 3
        assert ret[0] == pytest.approx(0.05, abs=0.001)

    def test_log_returns(self):
        prices = [100, 110, 121]
        ret = ReturnNormaliser.log_returns(prices)
        assert len(ret) == 2
        assert all(r > 0 for r in ret)

    def test_excess_returns(self):
        ret = ReturnNormaliser.excess_returns([0.05, 0.03, -0.02], 0.01)
        assert ret[0] == pytest.approx(0.04, abs=0.001)

    def test_align_series(self):
        series = {"A": [1, 2, 3, 4], "B": [1, 2]}
        aligned = ReturnNormaliser.align_series(series)
        assert len(aligned["A"]) == 2
        assert len(aligned["B"]) == 2

    def test_fx_adjust(self):
        ret = ReturnNormaliser.currency_adjust([0.05, 0.03], [0.01, -0.02])
        assert ret[0] == pytest.approx(0.06, abs=0.001)

class TestCorrelationEngine:
    def test_perfect_correlation(self):
        returns = {"A": [0.01, 0.02, -0.01, 0.03, 0.01],
                   "B": [0.01, 0.02, -0.01, 0.03, 0.01]}
        cm = CorrelationEngine.compute_matrix(returns)
        assert cm.matrix[0][1] == pytest.approx(1.0, abs=0.01)

    def test_negative_correlation(self):
        returns = {"A": [0.01, 0.02, -0.01, 0.03],
                   "B": [-0.01, -0.02, 0.01, -0.03]}
        cm = CorrelationEngine.compute_matrix(returns)
        assert cm.matrix[0][1] < -0.9

    def test_rolling_correlation(self):
        np.random.seed(42)
        a = np.random.randn(100).tolist()
        b = np.random.randn(100).tolist()
        rc = CorrelationEngine.rolling_correlation(a, b, "A", "B", window=20)
        assert len(rc.correlations) == 81  # 100 - 20 + 1

    def test_matrix_diagonal_one(self):
        returns = {"X": [0.01, -0.02, 0.03], "Y": [0.02, 0.01, -0.01]}
        cm = CorrelationEngine.compute_matrix(returns)
        assert cm.matrix[0][0] == pytest.approx(1.0, abs=0.01)

class TestMultiAssetEngine:
    def test_register_and_universe(self):
        eng = MultiAssetEngine()
        eng.register_asset(AssetProfile(ticker="SPY", asset_class=AssetClass.EQUITY))
        eng.register_asset(AssetProfile(ticker="TLT", asset_class=AssetClass.FIXED_INCOME))
        u = eng.get_universe()
        assert u.total_assets == 2
        assert "equity" in u.by_class

    def test_normalise_and_correlate(self):
        prices = {"A": [100, 102, 101, 104, 103], "B": [50, 51, 50, 52, 51]}
        cm = MultiAssetEngine.normalise_and_correlate(prices)
        assert len(cm.tickers) == 2
        assert len(cm.matrix) == 2
