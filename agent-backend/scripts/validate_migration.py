"""
scripts/validate_migration.py
─────────────────────────────────────────────────────────────────────────────
Post-migration validation script.
Compares SQLite source against PostgreSQL destination.

Usage:
    python -m scripts.validate_migration
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from src.config import get_settings


def validate():
    # Source: SQLite
    sqlite_path = Path(__file__).parent.parent / "advisers.db"
    if not sqlite_path.exists():
        print(f"[SKIP] No SQLite database at {sqlite_path}")
        return

    src_engine = create_engine(
        f"sqlite:///{sqlite_path}", echo=False,
        connect_args={"check_same_thread": False},
    )
    SrcSession = sessionmaker(bind=src_engine)

    # Destination: PostgreSQL
    pg_url = get_settings().DATABASE_URL
    if "sqlite" in pg_url:
        print("[ERROR] DATABASE_URL points to SQLite, nothing to validate.")
        sys.exit(1)

    dst_engine = create_engine(pg_url, echo=False)
    DstSession = sessionmaker(bind=dst_engine)

    src_tables = set(inspect(src_engine).get_table_names())
    dst_tables = set(inspect(dst_engine).get_table_names())

    print("=" * 60)
    print("  POST-MIGRATION VALIDATION")
    print("=" * 60)

    # 1. Table existence
    print("\n[1] Table Existence Check")
    missing = src_tables - dst_tables
    if missing:
        print(f"  [FAIL] Tables missing in PostgreSQL: {missing}")
    else:
        print(f"  [OK] All {len(src_tables)} tables present ✓")

    # 2. Row counts
    print("\n[2] Row Count Comparison")
    all_ok = True
    with SrcSession() as src_db, DstSession() as dst_db:
        for table in sorted(src_tables & dst_tables):
            src_count = src_db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            dst_count = dst_db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            status = "✓" if src_count == dst_count else "✗ MISMATCH"
            if src_count != dst_count:
                all_ok = False
            print(f"  {table:<35} SQLite={src_count:>6}  PG={dst_count:>6}  {status}")

    # 3. Boolean type check (signal_activations.is_expired)
    print("\n[3] Boolean Type Validation")
    with DstSession() as dst_db:
        try:
            result = dst_db.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'signal_activations' AND column_name = 'is_expired'"
            )).first()
            if result:
                dtype = result[1]
                status = "✓" if dtype == "boolean" else f"✗ Expected boolean, got {dtype}"
                print(f"  signal_activations.is_expired: {dtype}  {status}")
            else:
                print("  [SKIP] Column not found")
        except Exception as e:
            print(f"  [ERROR] {e}")

    # 4. Index check
    print("\n[4] Index Verification")
    pg_inspector = inspect(dst_engine)
    total_indexes = 0
    for table in sorted(dst_tables):
        indexes = pg_inspector.get_indexes(table)
        total_indexes += len(indexes)
    print(f"  Total custom indexes in PostgreSQL: {total_indexes}")

    # 5. Connection pool info
    print("\n[5] Connection Pool Status")
    print(f"  Pool size: {dst_engine.pool.size()}")
    print(f"  Overflow: {dst_engine.pool.overflow()}")
    print(f"  Checked-in: {dst_engine.pool.checkedin()}")

    print("\n" + "=" * 60)
    if all_ok:
        print("  VALIDATION PASSED ✓")
    else:
        print("  VALIDATION FAILED — see mismatches above")
    print("=" * 60)


if __name__ == "__main__":
    validate()
