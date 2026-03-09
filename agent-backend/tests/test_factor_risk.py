"""
tests/test_factor_risk.py — Factor Risk Decomposition tests.
"""
import numpy as np
import pytest
from src.engines.factor_risk.models import RiskFactor, FactorExposure
from src.engines.factor_risk.factor_model import FactorModel
from src.engines.factor_risk.risk_decomposer import RiskDecomposer
from src.engines.factor_risk.engine import FactorRiskEngine


# ── Helpers ──────────────────────────────────────────────────────────────────

def _synthetic_data(n_obs=252, seed=42):
    np.random.seed(seed)
    factor_returns = FactorRiskEngine.generate_synthetic_factors(n_obs, seed)
    factors = sorted(factor_returns.keys())
    F = np.array([factor_returns[f] for f in factors]).T

    # Generate asset returns with known factor loadings
    betas = {
        "AAPL": [1.1, 0.2, -0.1, 0.3, 0.1, 0.05],
        "MSFT": [1.0, -0.1, 0.2, 0.2, 0.3, -0.1],
        "JPM":  [0.9, 0.4, 0.5, -0.1, 0.2, 0.3],
        "JNJ":  [0.6, -0.2, 0.3, 0.0, 0.4, -0.2],
    }
    asset_returns = {}
    for ticker, b in betas.items():
        noise = np.random.randn(n_obs) * 0.005
        asset_returns[ticker] = (F @ np.array(b) + noise).tolist()

    return asset_returns, factor_returns


# ── Factor Model Tests ───────────────────────────────────────────────────────

class TestFactorModel:
    def test_estimate_exposures(self):
        asset_ret, factor_ret = _synthetic_data()
        exposures = FactorModel.estimate_exposures(asset_ret, factor_ret)
        assert len(exposures) == 4
        for exp in exposures:
            assert len(exp.exposures) == 6
            assert exp.r_squared > 0.3  # synthetic data should have decent R²

    def test_market_beta_near_true(self):
        asset_ret, factor_ret = _synthetic_data()
        exposures = FactorModel.estimate_exposures(asset_ret, factor_ret)
        exp_map = {e.ticker: e for e in exposures}
        # AAPL true market beta = 1.1
        assert abs(exp_map["AAPL"].exposures["market"] - 1.1) < 0.3

    def test_factor_covariance(self):
        _, factor_ret = _synthetic_data()
        factors, cov = FactorModel.compute_factor_covariance(factor_ret)
        assert len(factors) == 6
        assert cov.shape == (6, 6)
        # Covariance should be symmetric
        assert np.allclose(cov, cov.T)

    def test_residual_variance(self):
        asset_ret, factor_ret = _synthetic_data()
        exposures = FactorModel.estimate_exposures(asset_ret, factor_ret)
        resid = FactorModel.compute_residual_variance(asset_ret, factor_ret, exposures)
        assert len(resid) == 4
        for v in resid.values():
            assert v > 0


# ── Risk Decomposer Tests ───────────────────────────────────────────────────

class TestRiskDecomposer:
    def test_decompose(self):
        asset_ret, factor_ret = _synthetic_data()
        exposures = FactorModel.estimate_exposures(asset_ret, factor_ret)
        factors, cov = FactorModel.compute_factor_covariance(factor_ret)
        resid = FactorModel.compute_residual_variance(asset_ret, factor_ret, exposures)

        weights = {"AAPL": 0.3, "MSFT": 0.3, "JPM": 0.2, "JNJ": 0.2}
        decomp = RiskDecomposer.decompose(weights, exposures, cov, factors, resid)

        assert decomp.total_risk > 0
        assert decomp.systematic_risk > 0
        assert decomp.idiosyncratic_risk > 0
        assert decomp.systematic_pct > 0

    def test_contributions_sum(self):
        asset_ret, factor_ret = _synthetic_data()
        exposures = FactorModel.estimate_exposures(asset_ret, factor_ret)
        factors, cov = FactorModel.compute_factor_covariance(factor_ret)
        resid = FactorModel.compute_residual_variance(asset_ret, factor_ret, exposures)

        weights = {"AAPL": 0.3, "MSFT": 0.3, "JPM": 0.2, "JNJ": 0.2}
        decomp = RiskDecomposer.decompose(weights, exposures, cov, factors, resid)

        total_pct = sum(c.risk_pct for c in decomp.factor_contributions)
        assert abs(total_pct - 100) < 5  # should sum to ~100%

    def test_has_top_factors(self):
        asset_ret, factor_ret = _synthetic_data()
        exposures = FactorModel.estimate_exposures(asset_ret, factor_ret)
        factors, cov = FactorModel.compute_factor_covariance(factor_ret)
        resid = FactorModel.compute_residual_variance(asset_ret, factor_ret, exposures)

        weights = {"AAPL": 0.3, "MSFT": 0.3, "JPM": 0.2, "JNJ": 0.2}
        decomp = RiskDecomposer.decompose(weights, exposures, cov, factors, resid)

        assert len(decomp.top_risk_factors) > 0
        assert "market" in decomp.top_risk_factors  # market should dominate


# ── Engine Tests ─────────────────────────────────────────────────────────────

class TestFactorRiskEngine:
    def test_build_model(self):
        asset_ret, factor_ret = _synthetic_data()
        model = FactorRiskEngine.build_model(asset_ret, factor_ret)
        assert len(model.tickers) == 4
        assert len(model.factors) == 6
        assert len(model.exposures) == 4
        assert len(model.factor_covariance) == 6

    def test_decompose_risk(self):
        asset_ret, factor_ret = _synthetic_data()
        weights = {"AAPL": 0.25, "MSFT": 0.25, "JPM": 0.25, "JNJ": 0.25}
        decomp = FactorRiskEngine.decompose_risk(weights, asset_ret, factor_ret)
        assert decomp.total_risk > 0
        assert decomp.systematic_pct > 50  # factor-driven data, should be >50%

    def test_decompose_with_model(self):
        asset_ret, factor_ret = _synthetic_data()
        model = FactorRiskEngine.build_model(asset_ret, factor_ret)
        resid = FactorModel.compute_residual_variance(asset_ret, factor_ret, model.exposures)
        weights = {"AAPL": 0.4, "MSFT": 0.3, "JPM": 0.2, "JNJ": 0.1}
        decomp = FactorRiskEngine.decompose_with_model(weights, model, resid)
        assert decomp.total_risk > 0

    def test_synthetic_factors(self):
        factors = FactorRiskEngine.generate_synthetic_factors(100, seed=123)
        assert len(factors) == 6
        for f in factors.values():
            assert len(f) == 100

    def test_equal_weight_vs_concentrated(self):
        asset_ret, factor_ret = _synthetic_data()
        eq = FactorRiskEngine.decompose_risk(
            {"AAPL": 0.25, "MSFT": 0.25, "JPM": 0.25, "JNJ": 0.25},
            asset_ret, factor_ret,
        )
        conc = FactorRiskEngine.decompose_risk(
            {"AAPL": 0.7, "MSFT": 0.1, "JPM": 0.1, "JNJ": 0.1},
            asset_ret, factor_ret,
        )
        # Different allocations should produce different risk profiles
        assert eq.total_risk != conc.total_risk
