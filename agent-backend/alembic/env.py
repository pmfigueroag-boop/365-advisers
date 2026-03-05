"""
Alembic env.py — 365 Advisers
──────────────────────────────
Reads DATABASE_URL from application config (src.config.Settings)
and wires Alembic to the project's SQLAlchemy Base metadata
for autogenerate support.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ─── Alembic Config object ──────────────────────────────────────────────────
config = context.config

# Python logging from .ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ─── Import project metadata ────────────────────────────────────────────────
from src.data.database import Base  # noqa: E402
from src.config import get_settings  # noqa: E402

target_metadata = Base.metadata

# Override sqlalchemy.url from application config (not from alembic.ini)
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to actual DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
