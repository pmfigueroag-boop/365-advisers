"""tests/test_oms.py — Order Management System tests."""
import pytest
from src.engines.oms.models import OrderType, OrderSide, OrderStatus, Order, BrokerAccount, PortfolioPosition
from src.engines.oms.order_manager import OrderManager
from src.engines.oms.risk_checks import PreTradeRiskChecker
from src.engines.oms.engine import OMSEngine

class TestOrderManager:
    def test_create_order(self):
        om = OrderManager()
        o = om.create_order(ticker="AAPL", side=OrderSide.BUY, quantity=100)
        assert o.status == OrderStatus.PENDING
        assert o.ticker == "AAPL"
        assert om.total_orders == 1

    def test_submit_order(self):
        om = OrderManager()
        o = om.create_order(ticker="AAPL", side=OrderSide.BUY, quantity=100)
        submitted = om.submit_order(o.order_id)
        assert submitted.status == OrderStatus.SUBMITTED

    def test_fill_order(self):
        om = OrderManager()
        o = om.create_order(ticker="AAPL", side=OrderSide.BUY, quantity=100)
        om.submit_order(o.order_id)
        fill = om.fill_order(o.order_id, 175.0)
        assert fill is not None
        assert fill.fill_price == 175.0
        order = om.get_order(o.order_id)
        assert order.status == OrderStatus.FILLED

    def test_partial_fill(self):
        om = OrderManager()
        o = om.create_order(ticker="AAPL", side=OrderSide.BUY, quantity=100)
        om.submit_order(o.order_id)
        om.fill_order(o.order_id, 175.0, fill_quantity=50)
        order = om.get_order(o.order_id)
        assert order.status == OrderStatus.PARTIAL
        assert order.filled_quantity == 50

    def test_cancel_order(self):
        om = OrderManager()
        o = om.create_order(ticker="AAPL", side=OrderSide.BUY, quantity=100)
        assert om.cancel_order(o.order_id)
        assert om.get_order(o.order_id).status == OrderStatus.CANCELLED

    def test_cannot_fill_cancelled(self):
        om = OrderManager()
        o = om.create_order(ticker="AAPL", side=OrderSide.BUY, quantity=100)
        om.cancel_order(o.order_id)
        assert om.fill_order(o.order_id, 175.0) is None

    def test_open_orders(self):
        om = OrderManager()
        om.create_order(ticker="AAPL", side=OrderSide.BUY, quantity=100)
        om.create_order(ticker="MSFT", side=OrderSide.BUY, quantity=50)
        assert len(om.get_open_orders()) == 2

class TestRiskChecks:
    def test_buying_power_pass(self):
        acct = BrokerAccount(buying_power=100_000)
        order = Order(ticker="AAPL", side=OrderSide.BUY, quantity=100)
        r = PreTradeRiskChecker.check_buying_power(order, acct, 175.0)
        assert r.passed  # 17500 < 100000

    def test_buying_power_fail(self):
        acct = BrokerAccount(buying_power=10_000)
        order = Order(ticker="AAPL", side=OrderSide.BUY, quantity=100)
        r = PreTradeRiskChecker.check_buying_power(order, acct, 175.0)
        assert not r.passed  # 17500 > 10000

    def test_order_size_fail(self):
        order = Order(ticker="AAPL", side=OrderSide.BUY, quantity=1000)
        r = PreTradeRiskChecker.check_order_size(order, 175.0)
        assert not r.passed  # 175000 > 100000

    def test_concentration_fail(self):
        acct = BrokerAccount(total_equity=100_000, positions=[
            PortfolioPosition(ticker="AAPL", market_value=9_000)
        ])
        order = Order(ticker="AAPL", side=OrderSide.BUY, quantity=20)
        r = PreTradeRiskChecker.check_concentration(order, acct, 100.0)
        assert not r.passed  # (9000 + 2000) / 100000 = 11% > 10%

    def test_all_checks(self):
        acct = BrokerAccount(buying_power=50_000, total_equity=500_000)
        order = Order(ticker="AAPL", side=OrderSide.BUY, quantity=50)
        results = PreTradeRiskChecker.run_all(order, acct, 150.0)
        assert len(results) == 3
        assert PreTradeRiskChecker.all_passed(results)

class TestOMSEngine:
    def test_place_and_fill(self):
        oms = OMSEngine(BrokerAccount(cash=500_000, buying_power=500_000, total_equity=500_000))
        result = oms.place_order("AAPL", "buy", 50, 150.0)
        assert result["status"] == "submitted"
        order_id = result["order"]["order_id"]
        fill = oms.simulate_fill(order_id, 150.0)
        assert fill is not None
        assert oms.account.cash < 500_000

    def test_rejected_for_size(self):
        oms = OMSEngine(BrokerAccount(cash=500_000, buying_power=500_000, total_equity=500_000))
        result = oms.place_order("AAPL", "buy", 1000, 200.0)  # 200K > 100K limit
        assert result["status"] == "rejected"
