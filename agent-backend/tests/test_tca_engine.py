"""
tests/test_tca_engine.py — Tests for Transaction Cost Analysis engine.
"""
from __future__ import annotations
import pytest
from datetime import date
from src.engines.portfolio.tca import TCAEngine, OrderFill, TCAReport, FillAnalysis


def _fill(ticker="AAPL", side="BUY", dec=150.0, fill=150.30, shares=100, vwap=149.80):
    return OrderFill(
        order_id=f"{ticker}-001", ticker=ticker, side=side,
        decision_price=dec, fill_price=fill, shares=shares,
        vwap=vwap, fill_date=date(2026, 1, 15),
    )


class TestFillAnalysis:

    def test_buy_positive_is(self):
        """Buy: paid more than decision → positive IS."""
        tca = TCAEngine()
        a = tca.record_fill(_fill(dec=150, fill=150.30))
        assert a.implementation_shortfall_bps > 0

    def test_buy_negative_is(self):
        """Buy: paid less than decision → negative IS (good)."""
        tca = TCAEngine()
        a = tca.record_fill(_fill(dec=150, fill=149.70))
        assert a.implementation_shortfall_bps < 0

    def test_sell_is_direction(self):
        """Sell: received less than decision → positive IS (bad)."""
        tca = TCAEngine()
        a = tca.record_fill(_fill(side="SELL", dec=150, fill=149.50))
        assert a.implementation_shortfall_bps > 0

    def test_beat_vwap(self):
        """Fill below VWAP for buy → beat_vwap = True."""
        tca = TCAEngine()
        a = tca.record_fill(_fill(dec=150, fill=149.50, vwap=150))
        assert a.beat_vwap is True

    def test_slippage_dollars(self):
        tca = TCAEngine()
        a = tca.record_fill(_fill(dec=150, fill=150.50, shares=200))
        assert a.slippage_dollars == pytest.approx(100.0)  # 0.50 * 200

    def test_zero_decision_price(self):
        tca = TCAEngine()
        a = tca.record_fill(_fill(dec=0, fill=10))
        assert a.implementation_shortfall_bps == 0


class TestTCAReport:

    def test_aggregate_report(self):
        tca = TCAEngine()
        tca.record_fill(_fill("AAPL", "BUY", 150, 150.30, 100, 150))
        tca.record_fill(_fill("MSFT", "BUY", 400, 401.00, 50, 399))
        report = tca.analyze()
        assert report.total_fills == 2
        assert report.total_volume > 0

    def test_date_filtering(self):
        tca = TCAEngine()
        tca.record_fill(_fill())
        report = tca.analyze(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
        assert report.total_fills == 1

    def test_ticker_filtering(self):
        tca = TCAEngine()
        tca.record_fill(_fill("AAPL"))
        tca.record_fill(_fill("MSFT"))
        report = tca.analyze(ticker="AAPL")
        assert report.total_fills == 1

    def test_empty_report(self):
        tca = TCAEngine()
        report = tca.analyze()
        assert report.total_fills == 0

    def test_pct_beat_vwap(self):
        tca = TCAEngine()
        tca.record_fill(_fill(dec=150, fill=149.50, vwap=150))
        tca.record_fill(_fill(dec=150, fill=150.50, vwap=150))
        report = tca.analyze()
        assert report.pct_beat_vwap == 50.0

    def test_slippage_by_ticker(self):
        tca = TCAEngine()
        tca.record_fill(_fill("AAPL", dec=150, fill=150.50, shares=100))
        report = tca.analyze()
        assert "AAPL" in report.slippage_by_ticker

    def test_clear_fills(self):
        tca = TCAEngine()
        tca.record_fill(_fill())
        tca.clear()
        assert tca.fill_count == 0

    def test_worst_best_fill(self):
        tca = TCAEngine()
        tca.record_fill(_fill(dec=150, fill=152))     # Bad
        tca.record_fill(_fill(dec=150, fill=149.50))   # Good
        report = tca.analyze()
        assert report.worst_fill_bps > report.best_fill_bps
