"""
scripts/migrate_data.py
─────────────────────────────────────────────────────────────────────────────
Migrate data from SQLite (advisers.db) to PostgreSQL.

Usage:
    python -m scripts.migrate_data

Reads from the local SQLite file and writes to the PostgreSQL instance
defined by DATABASE_URL in the environment / .env file.

The script:
  1. Connects to both databases simultaneously
  2. Iterates tables in FK-dependency order
  3. Transforms SQLite-specific types (Integer booleans → Boolean)
  4. Bulk-inserts into PostgreSQL
  5. Reports row counts and validates integrity
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.config import get_settings


# ─── Table migration order (FK dependencies first) ──────────────────────────

MIGRATION_ORDER = [
    "portfolios",
    "portfolio_positions",         # FK → portfolios
    "backtest_runs",
    "backtest_results",            # FK → backtest_runs
    "signal_performance_events",   # FK → backtest_runs
    # Independent tables (no FK between them)
    "fundamental_analyses",
    "technical_analyses",
    "score_history",
    "opportunity_score_history",
    "ideas",
    "signal_snapshots",
    "composite_alpha_history",
    "signal_activations",
    "signal_calibration_history",
    "opportunity_alerts",
]


# ─── Type transformations ────────────────────────────────────────────────────

BOOLEAN_COLUMNS = {
    "signal_activations": ["is_expired"],
    "opportunity_alerts": ["read"],
}


def transform_row(table_name: str, row: dict) -> dict:
    """Apply type transformations for PostgreSQL compatibility."""
    if table_name in BOOLEAN_COLUMNS:
        for col in BOOLEAN_COLUMNS[table_name]:
            if col in row and row[col] is not None:
                row[col] = bool(row[col])
    return row


# ─── Main migration logic ───────────────────────────────────────────────────

def migrate():
    # Source: SQLite
    sqlite_path = Path(__file__).parent.parent / "advisers.db"
    if not sqlite_path.exists():
        print(f"[ERROR] SQLite database not found at {sqlite_path}")
        sys.exit(1)

    src_engine = create_engine(
        f"sqlite:///{sqlite_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    SrcSession = sessionmaker(bind=src_engine)

    # Destination: PostgreSQL
    pg_url = get_settings().DATABASE_URL
    if "sqlite" in pg_url:
        print("[ERROR] DATABASE_URL points to SQLite. Set it to PostgreSQL first.")
        print(f"  Current: {pg_url}")
        sys.exit(1)

    dst_engine = create_engine(pg_url, echo=False)
    DstSession = sessionmaker(bind=dst_engine)

    # Create schema on PostgreSQL
    print("[MIGRATE] Creating schema on PostgreSQL...")
    Base.metadata.create_all(dst_engine)

    src_inspector = inspect(src_engine)
    src_tables = set(src_inspector.get_table_names())

    total_migrated = 0
    results = []

    for table_name in MIGRATION_ORDER:
        if table_name not in src_tables:
            results.append((table_name, 0, "SKIPPED (not in SQLite)"))
            continue

        print(f"  [{table_name}] Reading from SQLite...")
        with SrcSession() as src_db:
            rows = src_db.execute(text(f"SELECT * FROM {table_name}")).mappings().all()
            row_count = len(rows)

        if row_count == 0:
            results.append((table_name, 0, "EMPTY"))
            continue

        print(f"  [{table_name}] Transforming {row_count} rows...")
        transformed = [transform_row(table_name, dict(r)) for r in rows]

        print(f"  [{table_name}] Writing to PostgreSQL...")
        with DstSession() as dst_db:
            # Clear existing data to allow re-run
            dst_db.execute(text(f"DELETE FROM {table_name}"))
            # Insert in batches of 500
            batch_size = 500
            columns = list(transformed[0].keys())
            col_str = ", ".join(columns)
            param_str = ", ".join(f":{c}" for c in columns)

            for i in range(0, len(transformed), batch_size):
                batch = transformed[i:i + batch_size]
                dst_db.execute(
                    text(f"INSERT INTO {table_name} ({col_str}) VALUES ({param_str})"),
                    batch,
                )
            dst_db.commit()

        total_migrated += row_count
        results.append((table_name, row_count, "OK"))
        print(f"  [{table_name}] ✓ {row_count} rows migrated")

    # ─── Report ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  MIGRATION REPORT")
    print("=" * 60)
    print(f"  {'Table':<35} {'Rows':>8}  {'Status'}")
    print("-" * 60)
    for table, count, status in results:
        print(f"  {table:<35} {count:>8}  {status}")
    print("-" * 60)
    print(f"  {'TOTAL':<35} {total_migrated:>8}")
    print("=" * 60)

    # Validate row counts
    print("\n[VALIDATE] Verifying row counts match...")
    mismatches = []
    with SrcSession() as src_db, DstSession() as dst_db:
        for table_name in MIGRATION_ORDER:
            if table_name not in src_tables:
                continue
            src_count = src_db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            try:
                dst_count = dst_db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            except Exception:
                dst_count = -1
            if src_count != dst_count:
                mismatches.append((table_name, src_count, dst_count))

    if mismatches:
        print("[WARNING] Row count mismatches found:")
        for table, src_c, dst_c in mismatches:
            print(f"  {table}: SQLite={src_c}, PostgreSQL={dst_c}")
    else:
        print("[OK] All row counts match ✓")

    print(f"\n[DONE] Migration completed at {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    migrate()
