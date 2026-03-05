"""
src/contracts/sizing.py
──────────────────────────────────────────────────────────────────────────────
Layer 5 output contracts — Position Sizing.
"""

from __future__ import annotations

from pydantic import BaseModel


class PositionAllocation(BaseModel):
    """Output of the Position Sizing Engine (Layer 5)."""
    opportunity_score: float = 0.0
    conviction_level: str = "Avoid"      # Very High, High, Moderate, Watch, Avoid
    risk_level: str = "Medium"           # Low, Medium, High, Extreme
    base_position_size: float = 0.0      # pre-adjustment %
    risk_adjustment: float = 0.75        # multiplier (0.25 – 1.0)
    suggested_allocation: float = 0.0    # final % after risk adjustment
    recommended_action: str = "Exit Position"  # Increase, Maintain, Reduce, Exit
