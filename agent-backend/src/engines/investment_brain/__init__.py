"""
src/engines/investment_brain/
──────────────────────────────────────────────────────────────────────────────
Investment Brain — Financial Decision Intelligence Module.

Integrates all Alpha engines into a unified interpretation layer that
produces market regime classifications, opportunity lists, portfolio
suggestions, risk alerts, and actionable investment insights.
"""

from src.engines.investment_brain.engine import InvestmentBrain
from src.engines.investment_brain.models import (
    InvestmentBrainDashboard,
    MarketRegime,
    RegimeClassification,
    DetectedOpportunity,
    OpportunityType,
    PortfolioSuggestion,
    PortfolioStyle,
    RiskAlert,
    RiskAlertType,
    InvestmentInsight,
    BrainAlert,
)

__all__ = [
    "InvestmentBrain",
    "InvestmentBrainDashboard",
    "MarketRegime",
    "RegimeClassification",
    "DetectedOpportunity",
    "OpportunityType",
    "PortfolioSuggestion",
    "PortfolioStyle",
    "RiskAlert",
    "RiskAlertType",
    "InvestmentInsight",
    "BrainAlert",
]
