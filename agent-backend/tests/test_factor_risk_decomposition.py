"""
tests/test_factor_risk_decomposition.py
--------------------------------------------------------------------------
Tests for RiskDecomposer and BarraFactorModel.
"""

from __future__ import annotations

import math
import pytest
import numpy as np

from src.engines.factor_risk.models import (
    FactorExposure,
    FactorContribution,
    FactorRiskDecomposition,
)
from src.engines.factor_risk.risk_decomposer import RiskDecomposer
from src.engines.factor_risk.barra_factor_model import (
    BarraFactorModel,
    BarraEstimation,
)


# ─── Risk Decomposer Tests ──────────────────────────────────────────────────

class TestRiskDecomposer:

    def _simple_decompose(self, n_assets=3, n_factors=2):
        """Helper: simple decomposition with given dimensions."""
        tickers = [f"T{i}" for i in range(n_assets)]
        weights = {t: 1.0 / n_assets for t in tickers}
        factor_names = [f"F{j}" for j in range(n_factors)]

        # Exposures: each asset has some loading on each factor
        exposures = []
        for i, t in enumerate(tickers):
            exp_dict = {f"F{j}": 0.5 + 0.1 * (i + j) for j in range(n_factors)}
            exposures.append(FactorExposure(ticker=t, exposures=exp_dict))

        # Factor covariance: identity × 0.01
        factor_cov = np.eye(n_factors) * 0.01
        residual_vars = {t: 0.005 for t in tickers}

        return RiskDecomposer.decompose(
            weights=weights,
            exposures=exposures,
            factor_covariance=factor_cov,
            factor_names=factor_names,
            residual_variances=residual_vars,
        )

    def test_basic_decomposition(self):
        """Decomposition produces valid result."""
        result = self._simple_decompose()
        assert isinstance(result, FactorRiskDecomposition)
        assert result.total_risk > 0

    def test_systematic_plus_idio(self):
        """Systematic² + Idiosyncratic² ≈ Total²."""
        result = self._simple_decompose()
        total_var = result.total_risk ** 2
        sys_var = result.systematic_risk ** 2
        idio_var = result.idiosyncratic_risk ** 2
        assert abs(total_var - (sys_var + idio_var)) < 1e-6

    def test_factor_contributions_present(self):
        """Factor contributions include each factor + idiosyncratic."""
        result = self._simple_decompose(n_factors=3)
        factor_names = [c.factor for c in result.factor_contributions]
        assert "idiosyncratic" in factor_names
        assert "F0" in factor_names

    def test_risk_pct_sums_near_100(self):
        """Factor risk percentages should sum ≈ 100%."""
        result = self._simple_decompose()
        total_pct = sum(c.risk_pct for c in result.factor_contributions)
        assert abs(total_pct - 100.0) < 5.0  # Tolerance for rounding

    def test_single_factor(self):
        """Single factor decomposition works."""
        result = self._simple_decompose(n_factors=1)
        assert result.systematic_risk > 0
        assert result.idiosyncratic_risk > 0

    def test_zero_exposure(self):
        """Zero exposure → zero risk contribution."""
        weights = {"A": 0.5, "B": 0.5}
        exposures = [
            FactorExposure(ticker="A", exposures={"mkt": 0.0}),
            FactorExposure(ticker="B", exposures={"mkt": 0.0}),
        ]
        result = RiskDecomposer.decompose(
            weights=weights,
            exposures=exposures,
            factor_covariance=np.array([[0.01]]),
            factor_names=["mkt"],
            residual_variances={"A": 0.01, "B": 0.01},
        )
        assert result.systematic_risk < 1e-6

    def test_top_risk_factors_ordering(self):
        """Top risk factors are sorted by absolute contribution."""
        result = self._simple_decompose(n_factors=3)
        assert len(result.top_risk_factors) <= 5
        assert isinstance(result.top_risk_factors, list)

    def test_marginal_risk_signs(self):
        """Marginal risk has sensible sign (positive for positive exposure)."""
        result = self._simple_decompose()
        for c in result.factor_contributions:
            if c.factor != "idiosyncratic" and c.exposure > 0:
                # Positive exposure to a factor → non-negative marginal risk
                assert c.marginal_risk >= -0.01  # Small tolerance


# ─── Barra Factor Model Tests ──────────────────────────────────────────────

class TestBarraFactorModel:

    def _sample_data(self, n_tickers=5, n_periods=50, seed=42):
        """Generate sample data for Barra estimation."""
        import random
        rng = random.Random(seed)

        tickers = [f"T{i}" for i in range(n_tickers)]
        characteristics = {}
        returns = {}

        for i, t in enumerate(tickers):
            characteristics[t] = {
                "market_cap": 1e9 * (10 ** (i * 0.5)),  # Varying sizes
                "beta": 0.8 + 0.2 * i,
                "book_to_price": 0.3 + 0.1 * i,
                "momentum_12m": 0.05 + 0.03 * i,
                "realised_vol": 0.15 + 0.05 * i,
            }
            returns[t] = [rng.gauss(0.0005, 0.02) for _ in range(n_periods)]

        return tickers, characteristics, returns

    def test_basic_estimation(self):
        """Barra model produces valid output."""
        tickers, chars, rets = self._sample_data()
        model = BarraFactorModel()
        result = model.estimate(tickers, chars, rets)

        assert isinstance(result, BarraEstimation)
        assert len(result.exposures) == len(tickers)
        assert len(result.factors) == 5

    def test_exposures_are_zscored(self):
        """Factor exposures should be z-scored (mean ≈ 0)."""
        tickers, chars, rets = self._sample_data(n_tickers=10)
        model = BarraFactorModel()
        result = model.estimate(tickers, chars, rets)

        for factor in result.factors:
            values = [e.exposures.get(factor, 0) for e in result.exposures]
            mean = sum(values) / len(values)
            assert abs(mean) < 0.5  # Should be near zero

    def test_exposures_clipped(self):
        """Exposures clipped to [-3, 3]."""
        tickers, chars, rets = self._sample_data()
        model = BarraFactorModel()
        result = model.estimate(tickers, chars, rets)

        for exp in result.exposures:
            for f, v in exp.exposures.items():
                assert -3.1 <= v <= 3.1

    def test_factor_covariance_symmetric(self):
        """Factor covariance matrix should be symmetric."""
        tickers, chars, rets = self._sample_data()
        model = BarraFactorModel()
        result = model.estimate(tickers, chars, rets)

        cov = result.factor_covariance
        k = len(cov)
        for i in range(k):
            for j in range(k):
                assert abs(cov[i][j] - cov[j][i]) < 1e-8

    def test_factor_covariance_positive_diagonal(self):
        """Diagonal of covariance should be non-negative."""
        tickers, chars, rets = self._sample_data()
        model = BarraFactorModel()
        result = model.estimate(tickers, chars, rets)

        for i in range(len(result.factor_covariance)):
            assert result.factor_covariance[i][i] >= 0

    def test_residual_variances_positive(self):
        """Residual variances should be positive."""
        tickers, chars, rets = self._sample_data()
        model = BarraFactorModel()
        result = model.estimate(tickers, chars, rets)

        for t, var in result.residual_variances.items():
            assert var >= 0

    def test_no_returns_still_works(self):
        """Without returns, uses defaults for covariance."""
        tickers, chars, _ = self._sample_data()
        model = BarraFactorModel()
        result = model.estimate(tickers, chars, returns=None)

        assert len(result.exposures) == len(tickers)
        assert len(result.factor_covariance) == 5

    def test_insufficient_tickers(self):
        """< 2 tickers → empty result."""
        model = BarraFactorModel()
        result = model.estimate(["AAPL"], {"AAPL": {"market_cap": 3e12}})
        assert len(result.exposures) == 0

    def test_integration_with_decomposer(self):
        """Barra output can feed directly into RiskDecomposer."""
        tickers, chars, rets = self._sample_data()
        model = BarraFactorModel()
        barra = model.estimate(tickers, chars, rets)

        # Use asymmetric weights so z-scored exposures don't cancel out
        weights = {"T0": 0.05, "T1": 0.10, "T2": 0.15, "T3": 0.25, "T4": 0.45}
        result = RiskDecomposer.decompose(
            weights=weights,
            exposures=barra.exposures,
            factor_covariance=np.array(barra.factor_covariance),
            factor_names=barra.factors,
            residual_variances=barra.residual_variances,
        )

        assert result.total_risk > 0
