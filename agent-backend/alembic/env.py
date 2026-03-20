"""
alembic/env.py
─────────────────────────────────────────────────────────────────────────────
Alembic migration environment — configured for 365 Advisers models.
Imports all model submodules so Alembic autogenerate can detect every table.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import Base and all model submodules so Alembic sees every table
from src.data.models.base import Base
from src.data.models import (  # noqa: F401
    analysis, portfolio, signals, backtesting,
    governance, operations,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    from src.config import get_settings
    url = str(get_settings().DATABASE_URL)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    from src.config import get_settings
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = str(get_settings().DATABASE_URL)
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
