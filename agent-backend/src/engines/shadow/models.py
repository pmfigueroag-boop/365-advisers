"""
src/engines/shadow/models.py
─────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Shadow Portfolio Framework.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ShadowPortfolioType(str, Enum):
    RESEARCH = "research"       # All IGE ideas
    BENCHMARK = "benchmark"     # Buy-and-hold SPY/sector ETF
    STRATEGY = "strategy"       # Named strategy ideas only


class SizingMethod(str, Enum):
    EQUAL_WEIGHT = "equal_weight"
    VOL_PARITY = "vol_parity"
    CONVICTION = "conviction"


class ShadowPortfolioCreate(BaseModel):
    name: str
    portfolio_type: ShadowPortfolioType
    strategy_id: str | None = None
    config: dict[str, Any] = Field(default_factory=lambda: {
        "rebalance_frequency": "weekly",
        "max_positions": 20,
        "sizing_method": "vol_parity",
        "max_single_position": 0.10,
        "max_sector_exposure": 0.25,
        "initial_nav": 100.0,
    })


class ShadowPositionSummary(BaseModel):
    ticker: str
    weight: float
    entry_price: float
    current_price: float | None = None
    entry_date: datetime
    exit_date: datetime | None = None
    pnl_pct: float = 0.0
    sizing_method: str = "vol_parity"


class ShadowSnapshotSummary(BaseModel):
    snapshot_date: datetime
    nav: float
    daily_return: float
    cumulative_return: float
    drawdown: float
    positions_count: int


class ShadowPortfolioSummary(BaseModel):
    portfolio_id: str
    name: str
    portfolio_type: ShadowPortfolioType
    strategy_id: str | None = None
    inception_date: datetime
    is_active: bool = True
    # Performance summary
    current_nav: float = 100.0
    total_return_pct: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    positions_count: int = 0
    # Latest positions
    positions: list[ShadowPositionSummary] = Field(default_factory=list)
