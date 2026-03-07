"""
src/data/external/contracts/etf_flows.py
──────────────────────────────────────────────────────────────────────────────
Normalized contracts for ETF flow data.

Captures sector, factor, and thematic rotations for use by the
Crowding Engine, Idea Generation Engine, and Alpha Signals.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ETFFlowEntry(BaseModel):
    """Single ETF flow observation."""
    etf_ticker: str
    date: str
    net_flow_usd: float
    aum: float | None = None
    flow_pct_aum: float | None = None


class SectorFlowSummary(BaseModel):
    """Aggregated flow data for a GICS sector."""
    sector: str
    net_flow_5d: float = 0.0
    net_flow_20d: float = 0.0
    flow_momentum: float = 0.0          # 5d mean vs 20d mean
    top_inflow_etfs: list[str] = Field(default_factory=list)
    top_outflow_etfs: list[str] = Field(default_factory=list)


class ETFFlowData(BaseModel):
    """
    Complete ETF flow snapshot.

    Consumed by:
      - CrowdingEngine (EFC indicator via net_flows)
      - Idea Generation (sector rotation detector)
      - Alpha Signals (flow category)
    """
    as_of: str = ""
    sector_flows: list[SectorFlowSummary] = Field(default_factory=list)
    factor_flows: dict[str, float] = Field(default_factory=dict)
    thematic_flows: dict[str, float] = Field(default_factory=dict)
    raw_entries: list[ETFFlowEntry] = Field(default_factory=list)
    source: str = "unknown"

    @classmethod
    def empty(cls) -> ETFFlowData:
        return cls(source="null")
