"""
src/engines/factor_risk/models.py — Factor Risk data contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class RiskFactor(str, Enum):
    """Standard Barra-style risk factors."""
    MARKET = "market"
    SIZE = "size"              # SMB
    VALUE = "value"            # HML
    MOMENTUM = "momentum"      # UMD
    QUALITY = "quality"        # RMW (profitability)
    VOLATILITY = "volatility"  # BAB (betting against beta)
    GROWTH = "growth"
    LEVERAGE = "leverage"
    LIQUIDITY = "liquidity"
    DIVIDEND_YIELD = "dividend_yield"
    BETA = "beta"
    RESIDUAL = "residual"      # idiosyncratic


class FactorExposure(BaseModel):
    """Per-asset factor loadings (betas)."""
    ticker: str
    exposures: dict[str, float] = Field(
        default_factory=dict,
        description="factor_name → loading (beta)",
    )
    r_squared: float = 0.0


class FactorContribution(BaseModel):
    """Factor's contribution to portfolio risk."""
    factor: str
    exposure: float = 0.0           # portfolio-level exposure
    factor_volatility: float = 0.0  # factor's own vol
    risk_contribution: float = 0.0  # absolute risk contribution
    risk_pct: float = 0.0           # % of total risk
    marginal_risk: float = 0.0      # marginal contribution


class FactorRiskDecomposition(BaseModel):
    """Full factor risk decomposition of a portfolio."""
    total_risk: float = 0.0
    systematic_risk: float = 0.0
    idiosyncratic_risk: float = 0.0
    systematic_pct: float = 0.0
    factor_contributions: list[FactorContribution] = Field(default_factory=list)
    top_risk_factors: list[str] = Field(default_factory=list)


class FactorModelResult(BaseModel):
    """Cross-sectional factor model output."""
    tickers: list[str] = Field(default_factory=list)
    factors: list[str] = Field(default_factory=list)
    exposures: list[FactorExposure] = Field(default_factory=list)
    factor_returns: dict[str, float] = Field(default_factory=dict)
    factor_covariance: list[list[float]] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
