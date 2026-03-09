"""
src/engines/oms/models.py — OMS data contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class Order(BaseModel):
    order_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    ticker: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: float = Field(gt=0)
    limit_price: float | None = None
    stop_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    strategy_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rejection_reason: str = ""

class Fill(BaseModel):
    fill_id: str = Field(default_factory=lambda: uuid4().hex[:8])
    order_id: str
    fill_price: float
    fill_quantity: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    commission: float = 0.0

class PortfolioPosition(BaseModel):
    ticker: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    weight: float = 0.0

class BrokerAccount(BaseModel):
    account_id: str = "default"
    cash: float = 1_000_000.0
    buying_power: float = 1_000_000.0
    total_equity: float = 1_000_000.0
    positions: list[PortfolioPosition] = Field(default_factory=list)

class RiskCheckResult(BaseModel):
    check_name: str
    passed: bool
    message: str = ""
    limit_value: float | None = None
    actual_value: float | None = None
