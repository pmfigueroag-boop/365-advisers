"""
src/data/external/contracts/geopolitical.py
──────────────────────────────────────────────────────────────────────────────
Normalized contracts for GDELT geopolitical event data.

Captures geopolitical risk indices, tone monitoring, country-level risk,
thematic analysis, and event spikes for macro overlay and regime context.

Consumed by:
  - Regime Weights Engine (macro risk overlay)
  - Decision Engine (CIO Memo geopolitical context)
  - Idea Generation (geopolitical shock detector)
  - Alpha Signals (geopolitical category)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ThemeRisk(BaseModel):
    """Risk assessment for a single GDELT theme."""
    theme: str                         # TRADE_WAR, SANCTIONS, CYBER_ATTACK, etc.
    tone: float = 0.0                  # avg GDELT tone (−10 to +10)
    event_count: int = 0
    trend: str = "stable"              # rising / falling / stable


class CountryRisk(BaseModel):
    """Country-level geopolitical risk summary."""
    country_code: str                  # ISO 2-letter
    country_name: str
    risk_level: str = "low"            # low / medium / high / critical
    event_count: int = 0
    tone: float = 0.0


class GeopoliticalEventData(BaseModel):
    """
    Complete geopolitical intelligence snapshot from GDELT.

    Consumed by:
      - Regime Weights Engine (macro risk overlay)
      - Decision Engine (CIO Memo geopolitical context)
      - Idea Generation Engine (geopolitical shock detector)
      - Alpha Signals (geopolitical category)
    """
    as_of: str = ""

    # Aggregate metrics
    risk_index: float | None = None            # 0–100 composite
    tone_avg_24h: float | None = None          # GDELT tone (−10 to +10)
    tone_avg_7d: float | None = None
    tone_momentum: float | None = None         # 24h vs 7d delta
    event_count_24h: int = 0
    event_count_7d: int = 0

    # Breakdown
    top_themes: list[ThemeRisk] = Field(default_factory=list)
    top_country_risks: list[CountryRisk] = Field(default_factory=list)

    # Spike detection
    spike_detected: bool = False               # event volume > 2σ above mean

    # Optional enrichment
    sector_exposure: dict[str, float] = Field(default_factory=dict)  # sector → risk linkage
    narrative_summary: str | None = None       # AI-generated 2-line summary

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls) -> GeopoliticalEventData:
        """Null-but-valid skeleton — engines skip geopolitical context."""
        return cls(source="null")
