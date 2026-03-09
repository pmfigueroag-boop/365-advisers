"""
tests/test_event_backtester.py — Event-driven backtester tests.
"""
import numpy as np
import pytest
from src.engines.event_backtester.models import MarketEvent, OrderEvent, BacktestConfig
from src.engines.event_backtester.event_bus import EventBus
from src.engines.event_backtester.execution_sim import ExecutionSimulator
from src.engines.event_backtester.engine import EventBacktester
from datetime import datetime, timezone


class TestEventBus:
    def test_emit_and_process(self):
        bus = EventBus()
        received = []
        from src.engines.event_backtester.models import EventType
        bus.register(EventType.MARKET, lambda e: received.append(e))
        event = MarketEvent(timestamp=datetime.now(timezone.utc), ticker="AAPL", price=175.0)
        bus.emit(event)
        assert bus.pending == 1
        bus.process_next()
        assert len(received) == 1

    def test_priority_order(self):
        bus = EventBus()
        order = []
        from src.engines.event_backtester.models import EventType
        bus.register(EventType.MARKET, lambda e: order.append("market"))
        bus.register(EventType.ORDER, lambda e: order.append("order"))
        bus.emit(OrderEvent(timestamp=datetime.now(timezone.utc), ticker="AAPL", side="buy", quantity=10))
        bus.emit(MarketEvent(timestamp=datetime.now(timezone.utc), ticker="AAPL", price=175.0))
        bus.process_all()
        assert order[0] == "market"  # market has higher priority

    def test_clear(self):
        bus = EventBus()
        bus.emit(MarketEvent(timestamp=datetime.now(timezone.utc), ticker="AAPL", price=175.0))
        bus.clear()
        assert bus.pending == 0


class TestExecutionSimulator:
    def test_market_order(self):
        config = BacktestConfig(commission_bps=5.0, slippage_bps=5.0)
        sim = ExecutionSimulator(config)
        order = OrderEvent(timestamp=datetime.now(timezone.utc), ticker="AAPL", side="buy", quantity=100)
        fill = sim.execute(order, 175.0)
        assert fill.ticker == "AAPL"
        assert fill.quantity == 100
        assert fill.fill_price > 0
        assert fill.commission > 0

    def test_buy_slippage_up(self):
        config = BacktestConfig(slippage_bps=10.0)
        sim = ExecutionSimulator(config)
        order = OrderEvent(timestamp=datetime.now(timezone.utc), ticker="AAPL", side="buy", quantity=100)
        fill = sim.execute(order, 100.0)
        assert fill.fill_price >= 100.0  # buys slip up

    def test_sell_slippage_down(self):
        config = BacktestConfig(slippage_bps=10.0)
        sim = ExecutionSimulator(config)
        order = OrderEvent(timestamp=datetime.now(timezone.utc), ticker="AAPL", side="sell", quantity=100)
        fill = sim.execute(order, 100.0)
        assert fill.fill_price <= 100.0  # sells slip down

    def test_limit_not_filled(self):
        config = BacktestConfig()
        sim = ExecutionSimulator(config)
        order = OrderEvent(timestamp=datetime.now(timezone.utc), ticker="AAPL", side="buy", quantity=100, order_type="limit", limit_price=170.0)
        fill = sim.execute_limit(order, 175.0)  # market above limit
        assert fill is None


class TestEventBacktester:
    def _prices(self, n=200):
        np.random.seed(42)
        return {"AAPL": (175 * np.cumprod(1 + np.random.randn(n) * 0.01)).tolist()}

    def test_run_returns_result(self):
        prices = self._prices()
        bt = EventBacktester()
        # Simple momentum strategy
        def strat(ticker, price, positions, cash, _h={}):
            _h.setdefault(ticker, [])
            _h[ticker].append(price)
            if len(_h[ticker]) < 20:
                return None
            sma = sum(_h[ticker][-20:]) / 20
            return 1.0 if price > sma else -1.0
        result = bt.run(prices, strat)
        assert result.events_processed > 0
        assert len(result.equity_curve) > 0
        assert result.final_equity > 0

    def test_equity_curve_length(self):
        prices = self._prices(100)
        bt = EventBacktester()
        result = bt.run(prices, lambda *a: None)
        assert len(result.equity_curve) == 100

    def test_initial_equity(self):
        config = BacktestConfig(initial_capital=500_000)
        bt = EventBacktester(config)
        result = bt.run(self._prices(10), lambda *a: None)
        assert result.equity_curve[0] == pytest.approx(500_000, abs=100)

    def test_no_trades_means_flat(self):
        bt = EventBacktester()
        result = bt.run(self._prices(50), lambda *a: None)
        assert result.total_trades == 0
        assert result.final_equity == pytest.approx(bt.config.initial_capital, abs=1)


class TestBacktestMetrics:
    def test_sharpe_computed(self):
        np.random.seed(42)
        prices = {"AAPL": (175 * np.cumprod(1 + np.random.randn(200) * 0.01 + 0.001)).tolist()}
        bt = EventBacktester()
        def strat(ticker, price, positions, cash, _h={}):
            _h.setdefault(ticker, [])
            _h[ticker].append(price)
            if len(_h[ticker]) < 20:
                return None
            return 1.0 if _h[ticker][-1] > _h[ticker][-5] else -1.0
        result = bt.run(prices, strat)
        assert isinstance(result.sharpe_ratio, float)

    def test_max_drawdown_nonneg(self):
        prices = {"AAPL": (175 * np.cumprod(1 + np.random.randn(100) * 0.01)).tolist()}
        bt = EventBacktester()
        result = bt.run(prices, lambda *a: None)
        assert result.max_drawdown >= 0
