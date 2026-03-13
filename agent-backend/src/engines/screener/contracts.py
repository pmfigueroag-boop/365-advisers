"""
src/engines/screener/contracts.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for the composable Screener Engine.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class FilterOperator(str, Enum):
    """Operators for filter criteria."""
    GT = "gt"           # greater than
    GTE = "gte"         # greater than or equal
    LT = "lt"           # less than
    LTE = "lte"         # less than or equal
    EQ = "eq"           # equal
    NEQ = "neq"         # not equal
    BETWEEN = "between" # between [value, value_max]
    IN = "in"           # value in list


class ScreenerFilter(BaseModel):
    """A single filter criterion."""
    field: str = Field(..., description="Field to filter on (e.g. 'pe_ratio', 'rsi', 'sector')")
    operator: FilterOperator = Field(..., description="Comparison operator")
    value: float | str | list = Field(..., description="Filter value (or [min, max] for BETWEEN)")
    value_max: float | None = Field(None, description="Max value for BETWEEN operator")

    def evaluate(self, actual: float | str | None) -> bool:
        """Evaluate this filter against an actual value."""
        if actual is None:
            return False

        if self.operator == FilterOperator.IN:
            return actual in (self.value if isinstance(self.value, list) else [self.value])

        if isinstance(actual, str) or isinstance(self.value, str):
            if self.operator == FilterOperator.EQ:
                return str(actual).upper() == str(self.value).upper()
            if self.operator == FilterOperator.NEQ:
                return str(actual).upper() != str(self.value).upper()
            return False

        val = float(self.value) if not isinstance(self.value, list) else 0.0
        act = float(actual)

        if self.operator == FilterOperator.GT:
            return act > val
        if self.operator == FilterOperator.GTE:
            return act >= val
        if self.operator == FilterOperator.LT:
            return act < val
        if self.operator == FilterOperator.LTE:
            return act <= val
        if self.operator == FilterOperator.EQ:
            return abs(act - val) < 1e-9
        if self.operator == FilterOperator.NEQ:
            return abs(act - val) >= 1e-9
        if self.operator == FilterOperator.BETWEEN:
            vmax = float(self.value_max) if self.value_max is not None else val
            return val <= act <= vmax

        return False


class ScreenerRequest(BaseModel):
    """Request payload for the screener endpoint."""
    filters: list[ScreenerFilter] = Field(default_factory=list)
    universe: str = Field("sp500", description="Universe to scan: sp500, nasdaq100, dow30, custom")
    custom_tickers: list[str] = Field(default_factory=list)
    sort_by: str = Field("score", description="Field to sort results by")
    sort_desc: bool = Field(True, description="Sort descending")
    limit: int = Field(50, ge=1, le=500, description="Max results to return")
    preset: str | None = Field(None, description="Pre-built screen name")


class ScreenerMatch(BaseModel):
    """A single ticker that passed all filters."""
    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    price: float | None = None
    market_cap: float | None = None
    # Scores
    fundamental_score: float | None = None
    technical_score: float | None = None
    composite_score: float | None = None
    # Filter details
    field_values: dict[str, float | str | None] = Field(default_factory=dict)
    filters_passed: int = 0
    filters_total: int = 0


class ScreenerResult(BaseModel):
    """Output of a screener run."""
    matches: list[ScreenerMatch] = Field(default_factory=list)
    total_scanned: int = 0
    total_passed: int = 0
    filters_applied: int = 0
    universe: str = ""
    preset: str | None = None
    processing_ms: float = 0.0
    available_fields: list[dict] | None = None
