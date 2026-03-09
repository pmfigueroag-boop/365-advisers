"""
src/data/external/contracts/alternative_signal.py
──────────────────────────────────────────────────────────────────────────────
Canonical contracts for alternative data signals.

Covers web traffic, app analytics, job postings, and other non-traditional
datasets from providers like Similarweb, Thinknum.

Consumed by:
  - Alpha Signals (alternative category)
  - Idea Generation (alternative edge detection)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class WebTrafficSignal(BaseModel):
    """Web traffic intelligence for a company's digital presence."""
    domain: str = ""
    monthly_visits: float | None = None
    visit_change_pct: float | None = None  # MoM
    avg_visit_duration_sec: float | None = None
    pages_per_visit: float | None = None
    bounce_rate: float | None = None
    country_breakdown: dict[str, float] = Field(default_factory=dict)  # country → pct


class AppSignal(BaseModel):
    """Mobile app analytics signal."""
    app_name: str = ""
    platform: str = ""                     # "ios", "android"
    downloads_estimate: float | None = None
    daily_active_users: float | None = None
    rating: float | None = None
    reviews_count: int | None = None


class JobPostingSignal(BaseModel):
    """Job posting trend signal for a company."""
    total_postings: int | None = None
    change_30d: float | None = None        # percent change
    top_categories: list[str] = Field(default_factory=list)
    hiring_velocity: str = "stable"        # accelerating, decelerating, stable


class AlternativeSignal(BaseModel):
    """
    Unified alternative data signal for a ticker.

    Stub-ready: commercial providers (Similarweb, Thinknum) require
    enterprise licenses. Adapter will populate when activated.
    """
    ticker: str

    # Sub-signals (populated by respective providers)
    web_traffic: WebTrafficSignal | None = None
    app_data: AppSignal | None = None
    job_postings: JobPostingSignal | None = None

    # Generic alternative data container
    custom_signals: dict[str, float] = Field(default_factory=dict)
    signal_descriptions: dict[str, str] = Field(default_factory=dict)

    # Overall alternative score
    composite_alt_score: float | None = None  # 0–100

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> AlternativeSignal:
        return cls(ticker=ticker, source="null")
