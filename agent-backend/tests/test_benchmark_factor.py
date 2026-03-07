"""
tests/test_benchmark_factor.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Benchmark & Factor Neutral Evaluation Model.

Covers:
  - FactorBuilder (factor construction from OHLCV)
  - FactorRegressor (OLS regression, alpha & betas)
  - BenchmarkFactorEngine (excess returns, alpha classification)
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.engines.backtesting.models import SignalEvent
from src.engines.alpha_signals.models import SignalStrength
from src.engines.benchmark_factor.factor_builder import FactorBuilder
from src.engines.benchmark_factor.regression import FactorRegressor
from src.engines.benchmark_factor.engine import BenchmarkFactorEngine
from src.engines.benchmark_factor.models import (
    AlphaSource,
    BenchmarkConfig,
    BenchmarkFactorReport,
    BenchmarkResult,
    FactorExposure,
    FactorTickers,
    SECTOR_MAP,
    SignalBenchmarkProfile,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_ohlcv(n_days: int = 252, base_price: float = 100.0, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    dates = pd.bdate_range(start="2023-01-02", periods=n_days)
    np.random.seed(seed)
    returns = np.random.normal(0.0005, 0.015, n_days)
    prices = base_price * np.cumprod(1 + returns)
    return pd.DataFrame({
        "Open": prices * 0.999,
        "High": prices * 1.01,
        "Low": prices * 0.99,
        "Close": prices,
        "Volume": np.random.randint(1_000_000, 10_000_000, n_days).astype(float),
    }, index=dates)


def _make_events(n: int = 30, signal_id: str = "test.signal") -> list[SignalEvent]:
    """Create synthetic signal events spread over time."""
    dates = pd.bdate_range(start="2023-03-01", periods=n, freq="5B")
    events = []
    np.random.seed(99)
    for i, d in enumerate(dates):
        fwd = np.random.normal(0.02, 0.05)
        bench = np.random.normal(0.01, 0.03)
        events.append(SignalEvent(
            signal_id=signal_id,
            ticker="AAPL",
            fired_date=d.date(),
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            value=50.0 + i,
            price_at_fire=150.0 + np.random.normal(0, 5),
            forward_returns={5: fwd * 0.3, 10: fwd * 0.6, 20: fwd},
            benchmark_returns={5: bench * 0.3, 10: bench * 0.6, 20: bench},
            excess_returns={5: (fwd - bench) * 0.3, 10: (fwd - bench) * 0.6, 20: fwd - bench},
        ))
    return events


# ─── Factor Builder Tests ───────────────────────────────────────────────────

class TestFactorBuilder:
    """Tests for factor return series construction."""

    def test_build_returns_four_columns(self):
        tickers = FactorTickers()
        ohlcv_data = {
            tickers.market: _make_ohlcv(seed=1),
            tickers.small_cap: _make_ohlcv(seed=2),
            tickers.value: _make_ohlcv(seed=3),
            tickers.growth: _make_ohlcv(seed=4),
            tickers.momentum: _make_ohlcv(seed=5),
        }
        builder = FactorBuilder()
        df = builder.build(ohlcv_data, tickers)

        assert "MKT" in df.columns
        assert "SMB" in df.columns
        assert "HML" in df.columns
        assert "UMD" in df.columns
        assert len(df) > 200

    def test_smb_is_small_minus_big(self):
        tickers = FactorTickers()
        ohlcv_data = {
            tickers.market: _make_ohlcv(seed=1),
            tickers.small_cap: _make_ohlcv(seed=2),
            tickers.value: _make_ohlcv(seed=3),
            tickers.growth: _make_ohlcv(seed=4),
            tickers.momentum: _make_ohlcv(seed=5),
        }
        builder = FactorBuilder()
        df = builder.build(ohlcv_data, tickers)

        # SMB = small_cap returns - market returns
        small_rets = ohlcv_data[tickers.small_cap]["Close"].pct_change().dropna()
        mkt_rets = ohlcv_data[tickers.market]["Close"].pct_change().dropna()
        expected_smb = small_rets - mkt_rets
        # Check first value matches
        assert abs(df["SMB"].iloc[0] - expected_smb.iloc[0]) < 1e-10

    def test_empty_data_returns_empty(self):
        builder = FactorBuilder()
        df = builder.build({})
        assert df.empty

    def test_get_factor_at_date(self):
        tickers = FactorTickers()
        ohlcv_data = {
            tickers.market: _make_ohlcv(seed=1),
            tickers.small_cap: _make_ohlcv(seed=2),
            tickers.value: _make_ohlcv(seed=3),
            tickers.growth: _make_ohlcv(seed=4),
            tickers.momentum: _make_ohlcv(seed=5),
        }
        builder = FactorBuilder()
        df = builder.build(ohlcv_data, tickers)

        result = builder.get_factor_at_date(df, df.index[10], window=20)
        assert result is not None
        assert "MKT" in result
        assert "SMB" in result


# ─── Factor Regressor Tests ─────────────────────────────────────────────────

class TestFactorRegressor:
    """Tests for OLS factor regression."""

    def test_known_alpha(self):
        """Signal returns = alpha + noise → should recover alpha."""
        np.random.seed(42)
        n = 100
        alpha = 0.01
        noise = np.random.normal(0, 0.005, n)
        # Factor matrix: random but uncorrelated with signal
        X = np.random.normal(0, 0.02, (n, 4))
        y = alpha + noise  # No factor exposure

        regressor = FactorRegressor()
        exposure = regressor.regress(y, X)

        assert abs(exposure.factor_alpha - alpha) < 0.005
        assert exposure.r_squared < 0.2  # Factors shouldn't explain much
        assert exposure.n_observations == n

    def test_known_beta(self):
        """Signal returns = β_MKT × MKT → should recover beta."""
        np.random.seed(42)
        n = 100
        true_beta = 1.5
        mkt = np.random.normal(0.005, 0.02, n)
        smb = np.random.normal(0, 0.01, n)
        hml = np.random.normal(0, 0.01, n)
        umd = np.random.normal(0, 0.01, n)
        X = np.column_stack([mkt, smb, hml, umd])
        y = true_beta * mkt + np.random.normal(0, 0.002, n)

        regressor = FactorRegressor()
        exposure = regressor.regress(y, X)

        assert abs(exposure.beta_market - true_beta) < 0.3
        assert exposure.r_squared > 0.5  # Should explain well

    def test_insufficient_data(self):
        regressor = FactorRegressor()
        exposure = regressor.regress(np.array([0.01]), np.array([[0.02, 0.01, 0, 0]]))
        assert exposure.n_observations == 1
        assert exposure.factor_alpha == 0.0

    def test_alpha_significance(self):
        np.random.seed(42)
        n = 200
        alpha = 0.05  # Very large alpha
        X = np.random.normal(0, 0.02, (n, 4))
        y = alpha + np.random.normal(0, 0.01, n)

        regressor = FactorRegressor()
        exposure = regressor.regress(y, X)

        assert exposure.alpha_significant is True
        assert abs(exposure.alpha_t_stat) > 2.0


# ─── Engine Tests ────────────────────────────────────────────────────────────

class TestBenchmarkFactorEngine:
    """Tests for the benchmark & factor evaluation engine."""

    def test_evaluate_basic(self):
        events = _make_events(30)
        ohlcv_data = {
            "AAPL": _make_ohlcv(seed=10),
            "SPY": _make_ohlcv(seed=11),
            "QQQ": _make_ohlcv(seed=12),
            "IWM": _make_ohlcv(seed=13),
            "IWD": _make_ohlcv(seed=14),
            "IWF": _make_ohlcv(seed=15),
            "MTUM": _make_ohlcv(seed=16),
            "XLK": _make_ohlcv(seed=17),
        }
        config = BenchmarkConfig(
            additional_benchmarks=["QQQ", "IWM"],
            enable_factor_regression=True,
        )
        engine = BenchmarkFactorEngine(config)
        report = engine.evaluate(events, ohlcv_data, config)

        assert isinstance(report, BenchmarkFactorReport)
        assert len(report.signal_profiles) == 1
        profile = report.signal_profiles[0]
        assert profile.signal_id == "test.signal"
        assert profile.total_events == 30
        assert len(profile.benchmark_results) >= 1

    def test_alpha_classification_pure(self):
        exposure = FactorExposure(
            alpha_significant=True, r_squared=0.10,
        )
        result = BenchmarkFactorEngine._classify_alpha(exposure)
        assert result == AlphaSource.PURE_ALPHA

    def test_alpha_classification_mixed(self):
        exposure = FactorExposure(
            alpha_significant=True, r_squared=0.50,
        )
        result = BenchmarkFactorEngine._classify_alpha(exposure)
        assert result == AlphaSource.MIXED

    def test_alpha_classification_factor(self):
        exposure = FactorExposure(alpha_significant=False, r_squared=0.80)
        result = BenchmarkFactorEngine._classify_alpha(exposure)
        assert result == AlphaSource.FACTOR_BETA

    def test_classify_none_exposure(self):
        result = BenchmarkFactorEngine._classify_alpha(None)
        assert result == AlphaSource.FACTOR_BETA


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestBFModels:
    """Tests for Pydantic model contracts."""

    def test_config_defaults(self):
        cfg = BenchmarkConfig()
        assert cfg.market_benchmark == "SPY"
        assert "QQQ" in cfg.additional_benchmarks
        assert cfg.enable_factor_regression is True
        assert cfg.forward_window == 20

    def test_factor_tickers_defaults(self):
        t = FactorTickers()
        assert t.market == "SPY"
        assert t.small_cap == "IWM"
        assert t.value == "IWD"
        assert t.growth == "IWF"
        assert t.momentum == "MTUM"

    def test_sector_map_coverage(self):
        assert SECTOR_MAP["AAPL"] == "XLK"
        assert SECTOR_MAP["JPM"] == "XLF"
        assert SECTOR_MAP["XOM"] == "XLE"
        assert SECTOR_MAP["JNJ"] == "XLV"
        assert len(SECTOR_MAP) >= 70

    def test_benchmark_result_serialization(self):
        br = BenchmarkResult(
            benchmark_ticker="SPY",
            benchmark_name="S&P 500",
            excess_return={20: 0.005},
            information_ratio={20: 0.85},
        )
        d = br.model_dump()
        assert d["benchmark_ticker"] == "SPY"
        assert d["excess_return"][20] == 0.005

    def test_factor_exposure_defaults(self):
        fe = FactorExposure()
        assert fe.factor_neutrality == 1.0
        assert fe.alpha_significant is False


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestBFDatabaseTable:
    """Verify benchmark_factor_profiles table exists in the ORM."""

    def test_table_exists(self):
        from src.data.database import BenchmarkFactorProfileRecord
        assert BenchmarkFactorProfileRecord.__tablename__ == "benchmark_factor_profiles"
        cols = {c.name for c in BenchmarkFactorProfileRecord.__table__.columns}
        assert "run_id" in cols
        assert "signal_id" in cols
        assert "factor_alpha" in cols
        assert "alpha_t_stat" in cols
        assert "beta_market" in cols
        assert "beta_size" in cols
        assert "beta_value" in cols
        assert "beta_momentum" in cols
        assert "r_squared" in cols
        assert "alpha_source" in cols
