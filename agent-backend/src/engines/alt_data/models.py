"""
src/engines/alt_data/models.py — Alternative data contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class AltDataType(str, Enum):
    SATELLITE = "satellite"
    WEB_TRAFFIC = "web_traffic"
    SOCIAL_SENTIMENT = "social_sentiment"
    CREDIT_CARD = "credit_card"
    JOB_POSTINGS = "job_postings"
    PATENT_FILINGS = "patent_filings"
    APP_DOWNLOADS = "app_downloads"
    SUPPLY_CHAIN = "supply_chain"


class AltDataSource(BaseModel):
    source_type: AltDataType
    name: str = ""
    enabled: bool = True
    api_key: str = ""
    freshness_hours: int = 24  # how old data can be


class AltDataSignal(BaseModel):
    ticker: str
    source_type: AltDataType
    signal: float = 0.0        # -1 to +1
    confidence: float = 0.0
    value: float = 0.0         # raw metric value
    change_pct: float = 0.0    # % change vs prior period
    z_score: float = 0.0       # standardised deviation
    description: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AltDataReport(BaseModel):
    ticker: str
    signals: list[AltDataSignal] = Field(default_factory=list)
    composite_signal: float = 0.0
    composite_confidence: float = 0.0
    sources_available: int = 0
    sources_used: int = 0
