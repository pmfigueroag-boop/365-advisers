"""
src/engines/attribution/models.py — Performance attribution data contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class SectorAttribution(BaseModel):
    """Per-sector Brinson-Fachler decomposition."""
    sector: str
    portfolio_weight: float = 0.0
    benchmark_weight: float = 0.0
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    allocation_effect: float = 0.0      # weight decision contribution
    selection_effect: float = 0.0       # stock picking contribution
    interaction_effect: float = 0.0     # cross term
    total_effect: float = 0.0


class BrinsonResult(BaseModel):
    """Full Brinson-Fachler attribution result."""
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0          # alpha = portfolio - benchmark
    total_allocation: float = 0.0
    total_selection: float = 0.0
    total_interaction: float = 0.0
    sector_attribution: list[SectorAttribution] = Field(default_factory=list)
    top_contributors: list[str] = Field(default_factory=list)
    top_detractors: list[str] = Field(default_factory=list)


class AttributionPeriod(BaseModel):
    """Multi-period attribution."""
    period: str = ""  # "2024-Q1", "2024-01"
    result: BrinsonResult = Field(default_factory=BrinsonResult)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
