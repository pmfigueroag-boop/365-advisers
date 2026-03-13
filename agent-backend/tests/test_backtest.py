"""
tests/test_backtest.py
──────────────────────────────────────────────────────────────────────────────
Tests for SignalLogger, BacktestTracker, IVSpread, and WalkForward.
"""

from __future__ import annotations

import pytest
import json
import tempfile
import os

from src.engines.technical.signal_logger import SignalLogger, SignalRecord
from src.engines.technical.backtest_tracker import (
    compute_forward_returns,
    compute_backtest_summary,
    ForwardReturns,
    BacktestSummary,
)
from src.engines.technical.iv_spread import IVSpreadModule, IVSpreadResult
from src.engines.technical.walk_forward import (
    optimize_params,
    get_current_params,
    DEFAULT_SIGMOID_PARAMS,
    WalkForwardResult,
    MIN_SIGNALS_FOR_OPTIMIZATION,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_signal(ticker="AAPL", signal="BUY", score=7.0, sq=0.7, price=150.0) -> SignalRecord:
    return SignalRecord(
        ticker=ticker,
        timestamp="2026-01-15T10:00:00Z",
        signal=signal,
        score=score,
        setup_quality=sq,
        confidence=0.7,
        regime="TRENDING",
        module_scores={"trend": 7.2, "momentum": 6.0},
        price_at_signal=price,
        bias="BULLISH",
    )


def _make_ohlcv_after_signal(start_price: float, returns_pct: list[float]) -> list[dict]:
    """Generate OHLCV data with specified daily returns."""
    data = []
    price = start_price
    for r in returns_pct:
        price *= (1 + r / 100)
        data.append({
            "open": price * 0.999,
            "high": price * 1.005,
            "low": price * 0.995,
            "close": round(price, 2),
            "volume": 1_000_000,
        })
    return data


# ─── Signal Logger Tests ─────────────────────────────────────────────────────

class TestSignalLogger:

    def test_log_and_count(self):
        logger = SignalLogger()
        logger.log(_make_signal())
        assert logger.count == 1

    def test_get_all(self):
        logger = SignalLogger()
        logger.log(_make_signal("AAPL"))
        logger.log(_make_signal("MSFT"))
        assert len(logger.get_all()) == 2

    def test_get_history_by_ticker(self):
        logger = SignalLogger()
        logger.log(_make_signal("AAPL"))
        logger.log(_make_signal("MSFT"))
        history = logger.get_history("AAPL")
        assert len(history) == 1
        assert history[0].ticker == "AAPL"

    def test_clear(self):
        logger = SignalLogger()
        logger.log(_make_signal())
        logger.clear()
        assert logger.count == 0

    def test_file_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            logger1 = SignalLogger(persist_path=path)
            logger1.log(_make_signal("AAPL"))
            logger1.log(_make_signal("MSFT"))

            # New logger from same file
            logger2 = SignalLogger(persist_path=path)
            loaded = logger2.load_from_file()
            assert loaded == 2
            assert logger2.count == 2
        finally:
            os.unlink(path)


# ─── Backtest Tracker Tests ──────────────────────────────────────────────────

class TestBacktestTracker:

    def test_forward_returns_buy_positive(self):
        """BUY signal + price goes up → hit=True."""
        record = _make_signal(signal="BUY", price=100.0)
        future = _make_ohlcv_after_signal(100.0, [1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                                                     1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
        fr = compute_forward_returns(record, future)
        assert fr.return_5d is not None and fr.return_5d > 0
        assert fr.hit_5d is True
        assert fr.return_20d is not None and fr.return_20d > 0
        assert fr.hit_20d is True

    def test_forward_returns_sell_positive(self):
        """SELL signal + price goes down → hit=True."""
        record = _make_signal(signal="SELL", price=100.0)
        future = _make_ohlcv_after_signal(100.0, [-1] * 20)
        fr = compute_forward_returns(record, future)
        assert fr.hit_5d is True
        assert fr.hit_20d is True

    def test_forward_returns_buy_negative(self):
        """BUY signal + price goes down → hit=False."""
        record = _make_signal(signal="BUY", price=100.0)
        future = _make_ohlcv_after_signal(100.0, [-1] * 20)
        fr = compute_forward_returns(record, future)
        assert fr.hit_5d is False

    def test_insufficient_future_data(self):
        """Not enough future data → None returns."""
        record = _make_signal(price=100.0)
        future = _make_ohlcv_after_signal(100.0, [1, 1])
        fr = compute_forward_returns(record, future)
        assert fr.return_1d is not None
        assert fr.return_20d is None

    def test_backtest_summary_hit_rate(self):
        """Compute hit rate from multiple signals."""
        signals = []
        for i in range(10):
            # 7 wins, 3 losses
            ret = 5.0 if i < 7 else -5.0
            hit = i < 7
            signals.append(ForwardReturns(
                ticker="AAPL", signal_date=f"2026-01-{i+1:02d}", signal="BUY",
                score=7.0, setup_quality=0.7, price_at_signal=100,
                return_5d=ret, return_20d=ret, hit_5d=hit, hit_20d=hit,
            ))

        summary = compute_backtest_summary(signals)
        assert summary.total_signals == 10
        assert summary.hit_rate_20d == 0.7
        assert summary.avg_return_20d > 0

    def test_empty_summary(self):
        summary = compute_backtest_summary([])
        assert summary.total_signals == 0


# ─── IV Spread Tests ─────────────────────────────────────────────────────────

class TestIVSpread:

    def setup_method(self):
        self.module = IVSpreadModule()

    def test_no_iv_data_neutral(self):
        result = self.module.compute(150.0, {}, [])
        score, evidence = self.module.score(result)
        assert score == 5.0
        assert result.data_available is False

    def test_with_iv_data(self):
        ohlcv = []
        price = 100
        for _ in range(25):
            ohlcv.append({
                "open": price - 0.5, "high": price + 1, "low": price - 1,
                "close": price, "volume": 1_000_000,
            })
            price += 0.3

        result = self.module.compute(
            price, {"iv": 30.0, "iv_percentile": 60.0}, ohlcv,
        )
        assert result.data_available is True
        assert result.iv_current == 30.0
        assert result.rv_current is not None

    def test_elevated_iv_bearish(self):
        """High IV spread should produce lower score."""
        result = IVSpreadResult(
            iv_current=40.0, rv_current=20.0, iv_rv_spread=20.0,
            iv_percentile=85.0, status="ELEVATED_IV", data_available=True,
        )
        score, _ = self.module.score(result)
        assert score < 5.0  # bearish

    def test_cheap_iv_bullish(self):
        """Low IV spread should produce higher score."""
        result = IVSpreadResult(
            iv_current=15.0, rv_current=25.0, iv_rv_spread=-10.0,
            iv_percentile=15.0, status="CHEAP_IV", data_available=True,
        )
        score, _ = self.module.score(result)
        assert score > 5.0  # bullish

    def test_format_details(self):
        result = IVSpreadResult(iv_current=30.0, rv_current=25.0,
                                 iv_rv_spread=5.0, data_available=True)
        details = self.module.format_details(result)
        assert details["iv_current"] == 30.0
        assert details["data_available"] is True


# ─── Walk-Forward Tests ──────────────────────────────────────────────────────

class TestWalkForward:

    def test_default_params_exist(self):
        params = get_current_params()
        assert len(params) >= 6
        assert "sma200_distance" in params
        assert "rsi" in params

    def test_insufficient_data_returns_defaults(self):
        summary = BacktestSummary(total_signals=10)
        result = optimize_params(summary)
        assert result.status == "INSUFFICIENT_DATA"
        assert result.signals_used == 10
        assert len(result.optimized_params) >= 6

    def test_sufficient_data_optimizes(self):
        """With 100+ signals, walk-forward should attempt optimization."""
        signals = []
        for i in range(120):
            ret = 3.0 if i % 3 != 0 else -2.0
            signals.append(ForwardReturns(
                ticker="AAPL", signal_date=f"2026-01-{(i % 28)+1:02d}",
                signal="BUY", score=7.0, setup_quality=0.7,
                price_at_signal=100, return_20d=ret,
                hit_20d=(ret > 0),
            ))

        summary = BacktestSummary(
            total_signals=120,
            signals_with_returns=signals,
            sharpe_proxy_20d=0.8,
        )
        result = optimize_params(summary)
        assert result.status == "OPTIMIZED"
        assert result.signals_used == 120
        assert result.training_hit_rate > 0
        assert result.last_optimized != ""

    def test_min_signals_threshold(self):
        assert MIN_SIGNALS_FOR_OPTIMIZATION == 100
