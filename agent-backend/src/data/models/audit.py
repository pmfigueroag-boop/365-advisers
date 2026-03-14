"""
src/data/models/audit.py
─────────────────────────────────────────────────────────────────────────────
Audit log database model — stores API request audit trail for compliance.
"""

from __future__ import annotations

from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Index

from src.data.database import Base


class AuditLog(Base):
    """Audit trail entry for API requests."""
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_user", "username"),
        Index("idx_audit_path", "path"),
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    timestamp   = Column(String(50), nullable=False)
    method      = Column(String(10), nullable=False)           # GET, POST, etc.
    path        = Column(String(500), nullable=False)
    query_params = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Float, nullable=False)
    client_ip   = Column(String(50), nullable=True)
    user_agent  = Column(String(200), nullable=True)
    username    = Column(String(100), default="anonymous")
