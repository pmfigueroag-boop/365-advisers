"""
src/data/models/base.py
─────────────────────────────────────────────────────────────────────────────
Database engine, session factory, and declarative base.
All model modules import Base from here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# ─── Database setup ───────────────────────────────────────────────────────────

def _build_engine():
    """Create the SQLAlchemy engine from DATABASE_URL config."""
    from src.config import get_settings
    url = get_settings().DATABASE_URL

    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        return create_engine(
            url, echo=False,
            connect_args={"check_same_thread": False},
        )
    else:
        return create_engine(
            url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )


ENGINE = _build_engine()
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db():
    """Call once at startup to create all tables and declarative indexes."""
    # Import all model modules so their tables are registered with Base.metadata
    from src.data.models import analysis, portfolio, signals, backtesting  # noqa: F401
    from src.data.models import governance, operations  # noqa: F401

    Base.metadata.create_all(ENGINE)
    db_type = "PostgreSQL" if "postgresql" in str(ENGINE.url) else "SQLite"
    print(f"[DB] Database initialised ({db_type}) — {ENGINE.url.database}")
