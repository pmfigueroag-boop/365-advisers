"""src/engines/multi_asset/models.py — Multi-asset data contracts."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

class AssetClass(str, Enum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    COMMODITY = "commodity"
    FX = "fx"
    CRYPTO = "crypto"
    REAL_ESTATE = "real_estate"

class AssetProfile(BaseModel):
    ticker: str
    name: str = ""
    asset_class: AssetClass = AssetClass.EQUITY
    currency: str = "USD"
    sector: str = ""
    country: str = "US"
    description: str = ""

class CorrelationMatrix(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    matrix: list[list[float]] = Field(default_factory=list)
    method: str = "pearson"
    window: int | None = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RollingCorrelation(BaseModel):
    ticker_a: str
    ticker_b: str
    window: int
    dates: list[str] = Field(default_factory=list)
    correlations: list[float] = Field(default_factory=list)

class MultiAssetUniverse(BaseModel):
    assets: list[AssetProfile] = Field(default_factory=list)
    by_class: dict[str, list[str]] = Field(default_factory=dict)
    total_assets: int = 0
