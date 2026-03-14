"""
src/data/models — Database model subpackages (bounded context separation).

This package contains domain-specific model files extracted from the
monolithic database.py. The models are imported here for backwards
compatibility — existing code continues to import from src.data.database.

Model domains:
  - audit.py   → AuditLog (API request audit trail)
  - (future)   → FundamentalAnalysis, TechnicalAnalysis, etc.
"""

from src.data.models.audit import AuditLog

__all__ = ["AuditLog"]
