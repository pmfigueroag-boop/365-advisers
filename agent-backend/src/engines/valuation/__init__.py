"""
src/engines/valuation/
──────────────────────────────────────────────────────────────────────────────
Intrinsic Valuation Engine — DCF, comparable analysis, margin of safety.

Provides:
  • Multi-stage DCF (growth → fade → terminal → discount)
  • Comparable company analysis (PE, EV/EBITDA, P/FCF, PB)
  • Margin of safety calculator (Graham Number)
  • Valuation orchestrator
"""

from src.engines.valuation.models import (
    DCFInput,
    DCFResult,
    CashFlowProjection,
    SensitivityCell,
    ComparableInput,
    ComparableResult,
    PeerMultiple,
    MarginOfSafety,
    ValuationVerdict,
    ValuationReport,
)
from src.engines.valuation.dcf import DCFModel
from src.engines.valuation.comparable import ComparableAnalysis
from src.engines.valuation.margin_of_safety import MarginCalculator
from src.engines.valuation.engine import ValuationEngine

__all__ = [
    "DCFInput", "DCFResult", "CashFlowProjection", "SensitivityCell",
    "ComparableInput", "ComparableResult", "PeerMultiple",
    "MarginOfSafety", "ValuationVerdict", "ValuationReport",
    "DCFModel", "ComparableAnalysis", "MarginCalculator", "ValuationEngine",
]
