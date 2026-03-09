"""
src/engines/oms/risk_checks.py — Pre-trade risk validation.
"""
from __future__ import annotations
import logging
from src.engines.oms.models import Order, BrokerAccount, RiskCheckResult

logger = logging.getLogger("365advisers.oms.risk_checks")


class PreTradeRiskChecker:
    """Pre-trade risk checks before order submission."""

    MAX_ORDER_VALUE = 100_000.0       # max single order value
    MAX_POSITION_WEIGHT = 0.10        # 10% max single position
    MAX_ORDERS_PER_TICKER = 5         # max open orders per ticker

    @classmethod
    def run_all(cls, order: Order, account: BrokerAccount, price: float) -> list[RiskCheckResult]:
        """Run all pre-trade checks. Returns list of results."""
        return [
            cls.check_buying_power(order, account, price),
            cls.check_order_size(order, price),
            cls.check_concentration(order, account, price),
        ]

    @classmethod
    def all_passed(cls, results: list[RiskCheckResult]) -> bool:
        return all(r.passed for r in results)

    @classmethod
    def check_buying_power(cls, order: Order, account: BrokerAccount, price: float) -> RiskCheckResult:
        order_value = order.quantity * price
        return RiskCheckResult(
            check_name="buying_power",
            passed=order_value <= account.buying_power,
            message=f"Order value ${order_value:,.0f} vs buying power ${account.buying_power:,.0f}",
            limit_value=account.buying_power,
            actual_value=order_value,
        )

    @classmethod
    def check_order_size(cls, order: Order, price: float) -> RiskCheckResult:
        order_value = order.quantity * price
        return RiskCheckResult(
            check_name="order_size",
            passed=order_value <= cls.MAX_ORDER_VALUE,
            message=f"Order value ${order_value:,.0f} vs limit ${cls.MAX_ORDER_VALUE:,.0f}",
            limit_value=cls.MAX_ORDER_VALUE,
            actual_value=order_value,
        )

    @classmethod
    def check_concentration(cls, order: Order, account: BrokerAccount, price: float) -> RiskCheckResult:
        order_value = order.quantity * price
        existing = sum(p.market_value for p in account.positions if p.ticker == order.ticker)
        total_exposure = existing + order_value
        weight = total_exposure / max(account.total_equity, 1)
        return RiskCheckResult(
            check_name="concentration",
            passed=weight <= cls.MAX_POSITION_WEIGHT,
            message=f"Position weight {weight:.1%} vs limit {cls.MAX_POSITION_WEIGHT:.1%}",
            limit_value=cls.MAX_POSITION_WEIGHT,
            actual_value=weight,
        )
