"""
tests/test_stat_arb.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Statistical Arbitrage / Pairs Trading engine.
"""

import numpy as np
import pytest

from src.engines.stat_arb.models import (
    PairCandidate,
    CointegrationResult,
    PairSpread,
    PairScanResult,
    ZScoreSignal,
)
from src.engines.stat_arb.cointegration import engle_granger_test, estimate_half_life
from src.engines.stat_arb.zscore import compute_spread, compute_zscore, generate_signals
from src.engines.stat_arb.scanner import PairScanner
from src.engines.stat_arb.engine import StatArbEngine


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_cointegrated_pair(n=300, noise_std=0.5):
    """Generate a synthetic cointegrated pair."""
    np.random.seed(42)
    b = np.cumsum(np.random.randn(n)) + 100  # random walk
    a = 1.5 * b + np.random.randn(n) * noise_std + 10  # cointegrated with B
    return a.tolist(), b.tolist()


def _make_independent_pair(n=300):
    """Generate two independent random walks (not cointegrated)."""
    np.random.seed(99)
    a = np.cumsum(np.random.randn(n)) + 100
    b = np.cumsum(np.random.randn(n)) + 100
    return a.tolist(), b.tolist()


# ── Cointegration Tests ──────────────────────────────────────────────────────

class TestCointegration:
    def test_cointegrated_pair(self):
        a, b = _make_cointegrated_pair()
        result = engle_granger_test(a, b)
        assert isinstance(result, CointegrationResult)
        assert result.is_cointegrated is True
        assert result.p_value < 0.05
        assert result.hedge_ratio != 0

    def test_non_cointegrated_pair(self):
        a, b = _make_independent_pair()
        result = engle_granger_test(a, b)
        assert result.is_cointegrated is False
        assert result.p_value > 0.05

    def test_short_series_handled(self):
        result = engle_granger_test([1, 2, 3], [4, 5, 6])
        assert result.is_cointegrated is False
        assert result.observations == 3

    def test_critical_values_present(self):
        a, b = _make_cointegrated_pair()
        result = engle_granger_test(a, b)
        assert "1%" in result.critical_values
        assert "5%" in result.critical_values
        assert "10%" in result.critical_values


class TestHalfLife:
    def test_mean_reverting_series(self):
        """Generate a known OU process and check half-life is reasonable."""
        np.random.seed(123)
        n = 500
        theta = 0.15  # stronger speed of reversion
        spread = [0.0]
        for _ in range(n - 1):
            spread.append(spread[-1] * (1 - theta) + np.random.randn() * 0.5)
        hl = estimate_half_life(spread)
        assert hl > 0  # should be positive for mean-reverting process
        assert hl < 100  # should be finite and reasonably bounded

    def test_random_walk_no_reversion(self):
        """Random walk should have zero or very long half-life."""
        np.random.seed(77)
        rw = np.cumsum(np.random.randn(200)).tolist()
        hl = estimate_half_life(rw)
        # Random walks are not mean-reverting: half-life should be 0 or extremely long
        assert hl == 0.0 or hl > 50


# ── Z-Score Tests ────────────────────────────────────────────────────────────

class TestZScore:
    def test_compute_spread(self):
        a = [100, 102, 104]
        b = [50, 51, 52]
        spread = compute_spread(a, b, hedge_ratio=2.0)
        np.testing.assert_array_almost_equal(spread, [0, 0, 0])

    def test_compute_zscore_shape(self):
        spread = np.random.randn(100).tolist()
        z = compute_zscore(spread, lookback=20)
        assert len(z) == 100
        assert z[0] == 0  # first points are zero (no lookback)

    def test_signal_generation_entry_exit(self):
        # Create z-scores that trigger entry and exit
        z = [0, 0, -2.5, -2.3, -1.0, -0.3, 0.0, 2.5, 2.3, 1.0, 0.3]
        signals = generate_signals(z, entry_threshold=2.0, exit_threshold=0.5)
        assert len(signals) == len(z)
        # First signals should be neutral
        assert signals[0] == ZScoreSignal.NEUTRAL
        # z=-2.5 should trigger LONG_A_SHORT_B
        assert signals[2] == ZScoreSignal.LONG_A_SHORT_B
        # After mean reversion, should EXIT
        exit_found = any(s == ZScoreSignal.EXIT for s in signals)
        assert exit_found


# ── Scanner Tests ────────────────────────────────────────────────────────────

class TestPairScanner:
    def test_basic_scan(self):
        # Generate 3 cointegrated pairs in same sector
        np.random.seed(42)
        b_base = np.cumsum(np.random.randn(200)) + 100
        prices = {
            "A": (1.5 * b_base + np.random.randn(200) * 0.3 + 10).tolist(),
            "B": b_base.tolist(),
            "C": (0.8 * b_base + np.random.randn(200) * 0.4 + 5).tolist(),
        }
        sector_map = {"A": "Tech", "B": "Tech", "C": "Tech"}

        result = PairScanner.scan(
            universe_prices=prices,
            sector_map=sector_map,
            min_correlation=0.5,
        )
        assert isinstance(result, PairScanResult)
        assert result.universe_size == 3
        assert result.pairs_tested > 0

    def test_cross_sector_excluded(self):
        np.random.seed(42)
        b = np.cumsum(np.random.randn(200)) + 100
        prices = {
            "A": (1.5 * b + np.random.randn(200) * 0.3).tolist(),
            "B": b.tolist(),
        }
        # Different sectors → no pairs tested
        sector_map = {"A": "Tech", "B": "Energy"}
        result = PairScanner.scan(prices, sector_map)
        assert result.pairs_tested == 0


# ── Engine Tests ─────────────────────────────────────────────────────────────

class TestStatArbEngine:
    def test_evaluate_pair(self):
        a, b = _make_cointegrated_pair()
        pair = StatArbEngine.evaluate_pair("AAPL", "MSFT", a, b)
        assert isinstance(pair, PairCandidate)
        assert pair.ticker_a == "AAPL"
        assert pair.ticker_b == "MSFT"
        assert pair.correlation != 0

    def test_construct_trade_with_signal(self):
        a, b = _make_cointegrated_pair()
        pair = StatArbEngine.evaluate_pair("A", "B", a, b)
        trade = StatArbEngine.construct_trade(pair, capital=100000)
        assert "signal" in trade
        # Trade may or may not have active legs depending on current z
        if pair.current_signal not in (ZScoreSignal.NEUTRAL, ZScoreSignal.EXIT):
            assert trade["long_leg"] is not None
            assert trade["short_leg"] is not None

    def test_construct_trade_neutral(self):
        # Force a neutral pair
        pair = PairCandidate(
            ticker_a="X", ticker_b="Y",
            current_signal=ZScoreSignal.NEUTRAL,
        )
        trade = StatArbEngine.construct_trade(pair)
        assert trade["long_leg"] is None
        assert trade["short_leg"] is None


# ── Model Validation Tests ───────────────────────────────────────────────────

class TestModelValidation:
    def test_cointegration_result_valid(self):
        r = CointegrationResult(
            ticker_a="A", ticker_b="B",
            test_statistic=-3.5, p_value=0.01,
            is_cointegrated=True,
        )
        assert r.is_cointegrated

    def test_pair_candidate_quality_score_range(self):
        p = PairCandidate(ticker_a="A", ticker_b="B", quality_score=75.5)
        assert 0 <= p.quality_score <= 100
