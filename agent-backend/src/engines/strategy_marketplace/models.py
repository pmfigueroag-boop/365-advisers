"""
src/engines/strategy_marketplace/models.py
─────────────────────────────────────────────────────────────────────────────
Strategy Marketplace — data models for published strategies.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ListingStatus(str, Enum):
    LISTED = "listed"
    DELISTED = "delisted"
    FEATURED = "featured"


class PublishedStrategy(BaseModel):
    """A strategy listing in the marketplace."""
    # Identity
    listing_id: str
    strategy_id: str
    name: str
    author: str = "system"
    description: str = ""
    strategy_type: str = ""
    version: str = "1.0.0"

    # Composition
    signals_used: list[str] = Field(default_factory=list)
    signal_categories: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)

    # Performance Summary
    backtest_summary: dict[str, Any] = Field(default_factory=dict)

    # Trust Badges
    trust_badges: dict[str, float] = Field(default_factory=dict)
    quality_grade: str = "C"

    # Metadata
    tags: list[str] = Field(default_factory=list)
    regime_compatibility: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    published_at: str | None = None
    updated_at: str | None = None
    download_count: int = 0
    status: ListingStatus = ListingStatus.LISTED
    marketplace_score: float = 0.0


class MarketplaceSearchParams(BaseModel):
    """Search/filter parameters for marketplace discovery."""
    search: str | None = None
    strategy_type: str | None = None
    risk_level: str | None = None
    min_quality_score: float | None = None
    min_sharpe: float | None = None
    max_drawdown: float | None = None
    regime: str | None = None
    signals: list[str] | None = None
    tags: list[str] | None = None
    sort_by: str = "marketplace_score"  # marketplace_score, sharpe, cagr, downloads, published_at, stability
    limit: int = 50
