"""
src/engines/sizing/__init__.py
──────────────────────────────────────────────────────────────────────────────
Position Sizing Engine (Layer 5) — renamed from portfolio sizing.
Re-exports the existing position_sizing module for clean imports.
"""

from src.engines.portfolio.position_sizing import PositionSizingModel

__all__ = ["PositionSizingModel"]

