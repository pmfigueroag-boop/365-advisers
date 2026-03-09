"""
src/engines/compliance/models.py — Compliance data contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class RuleType(str, Enum):
    RESTRICTED_LIST = "restricted_list"
    POSITION_LIMIT = "position_limit"
    SECTOR_LIMIT = "sector_limit"
    CONCENTRATION = "concentration"
    HOLDING_PERIOD = "holding_period"
    LEVERAGE = "leverage"
    TRADE_FREQUENCY = "trade_frequency"
    PRE_CLEARANCE = "pre_clearance"


class ComplianceRule(BaseModel):
    rule_id: str
    rule_type: RuleType
    description: str = ""
    enabled: bool = True
    params: dict = Field(default_factory=dict)


class ComplianceCheck(BaseModel):
    rule_id: str
    rule_type: RuleType
    passed: bool
    severity: str = "warning"  # info | warning | critical
    message: str = ""
    details: dict = Field(default_factory=dict)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ComplianceReport(BaseModel):
    total_rules: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    critical: int = 0
    is_compliant: bool = True
    checks: list[ComplianceCheck] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
