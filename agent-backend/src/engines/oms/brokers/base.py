"""
src/engines/oms/brokers/base.py
──────────────────────────────────────────────────────────────────────────────
Abstract Broker Adapter — pluggable interface for any broker.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable
from pydantic import BaseModel, Field
from src.engines.oms.models import Order, Fill, BrokerAccount, PortfolioPosition, OrderStatus


class BrokerType(str, Enum):
    PAPER = "paper"
    ALPACA = "alpaca"
    INTERACTIVE_BROKERS = "interactive_brokers"


class BrokerConfig(BaseModel):
    """Broker connection configuration."""
    broker_type: BrokerType = BrokerType.PAPER
    api_key: str = ""
    api_secret: str = ""
    base_url: str = ""
    paper_mode: bool = True
    max_retries: int = 3
    timeout_seconds: int = 30


class BrokerAdapter(ABC):
    """
    Abstract interface for broker connectivity.

    All broker implementations must implement these methods.
    The OMS Engine uses this interface to route orders.
    """

    def __init__(self, config: BrokerConfig):
        self.config = config
        self._connected = False

    @property
    def broker_type(self) -> BrokerType:
        return self.config.broker_type

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to broker. Returns True on success."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Cleanly disconnect from broker."""
        ...

    @abstractmethod
    async def submit_order(self, order: Order) -> str:
        """
        Submit an order to the broker.

        Args:
            order: Internal Order object.

        Returns:
            broker_order_id: External order ID from the broker.
        """
        ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order by its broker-assigned ID."""
        ...

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """Get the current status of an order from the broker."""
        ...

    @abstractmethod
    async def get_account(self) -> BrokerAccount:
        """Fetch current account state from broker."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[PortfolioPosition]:
        """Fetch all current positions from broker."""
        ...

    @abstractmethod
    async def get_quote(self, ticker: str) -> float:
        """Get the latest price for a ticker."""
        ...

    async def health_check(self) -> dict:
        """Check broker connectivity health."""
        return {
            "broker": self.broker_type.value,
            "connected": self.is_connected,
            "paper_mode": self.config.paper_mode,
        }
