#!/usr/bin/env python3
"""
Migrate all data from local SQLite to remote PostgreSQL (Supabase).

Usage (from backend/ directory):
    DATABASE_URL='postgresql+psycopg2://...' python3 -m scripts.migrate_sqlite_to_pg

    # Resume after interruption (skips already-migrated rows):
    DATABASE_URL='postgresql+psycopg2://...' python3 -m scripts.migrate_sqlite_to_pg --resume

    # Force fresh migration (clears target tables first):
    DATABASE_URL='postgresql+psycopg2://...' python3 -m scripts.migrate_sqlite_to_pg --clear

Requires:
  - Local SQLite database at data/neetpg.db (default) or set SQLITE_PATH env var
  - DATABASE_URL env var pointing to PostgreSQL (Supabase)
"""
import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.pool import NullPool

# --- Source: local SQLite ---
SQLITE_PATH = os.getenv("SQLITE_PATH", "data/neetpg.db")
if not os.path.exists(SQLITE_PATH):
    print(f"ERROR: SQLite database not found at {SQLITE_PATH}")
    print("Set SQLITE_PATH env var to the correct path.")
    sys.exit(1)

sqlite_engine = create_engine(
    f"sqlite:///{SQLITE_PATH}",
    connect_args={"check_same_thread": False},
)

# --- Target: PostgreSQL ---
PG_URL = os.getenv("DATABASE_URL")
if not PG_URL or "postgresql" not in PG_URL:
    print("ERROR: DATABASE_URL must be set to a PostgreSQL connection string.")
    sys.exit(1)

pg_engine = create_engine(
    PG_URL,
    poolclass=NullPool,  # No connection pooling - fresh connection each time
    connect_args={
        "connect_timeout": 30,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)

# Tables to migrate (in order to respect foreign key deps)
TABLES = [
    "institutes",
    "institute_mapping",
    "allotments",
    "ref_courses",
    "ingestion_progress",
    "ingestion_errors",
]

# Primary key column for each table (for resume support)
TABLE_PK = {
    "institutes": "institute_code",
    "institute_mapping": "db_institute_name",
    "allotments": "id",
    "ref_courses": "id",
    "ingestion_progress": "id",
    "ingestion_errors": "id",
}

BATCH_SIZE = int(os.getenv("MIGRATE_BATCH_SIZE", "50"))


def migrate_table(table_name: str, resume: bool = False):
    """Copy all rows from SQLite table to PostgreSQL."""
    sqlite_inspector = inspect(sqlite_engine)
    if table_name not in sqlite_inspector.get_table_names():
        print(f"  SKIP {table_name}: not found in SQLite")
        return

    with sqlite_engine.connect() as src:
        rows = src.execute(text(f"SELECT * FROM {table_name}")).fetchall()
        columns = src.execute(text(f"SELECT * FROM {table_name} LIMIT 0")).keys()
        col_names = list(columns)

    if not rows:
        print(f"  SKIP {table_name}: 0 rows in SQLite")
        return

    total = len(rows)

    # Check how many rows already exist in target
    existing_count = 0
    if resume:
        with pg_engine.connect() as dst:
            result = dst.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            existing_count = result.scalar()
        if existing_count >= total:
            print(f"  SKIP {table_name}: already complete ({existing_count}/{total})")
            return
        if existing_count > 0:
            print(f"  {table_name}: resuming from {existing_count}/{total}...")

    if not resume or existing_count == 0:
        # Fresh start: clear existing data
        with pg_engine.connect() as dst:
            dst.execute(text(f"DELETE FROM {table_name}"))
            dst.commit()
        existing_count = 0

    print(f"  {table_name}: {total - existing_count} rows to insert (total {total})...")

    # Build INSERT with ON CONFLICT DO NOTHING for resume safety
    pk = TABLE_PK.get(table_name, "id")

    # Skip already-inserted rows when resuming
    start_idx = existing_count if resume else 0
    inserted = 0
    retries = 0

    for i in range(start_idx, total, BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        params = [dict(zip(col_names, row)) for row in batch]

        # Build single INSERT ... VALUES (...), (...) statement per batch
        # This is much faster than executemany
        value_rows = []
        bind_params = {}
        for row_idx, row_dict in enumerate(params):
            row_placeholders = []
            for col in col_names:
                param_name = f"p{row_idx}_{col}"
                row_placeholders.append(f":{param_name}")
                bind_params[param_name] = row_dict[col]
            value_rows.append(f"({', '.join(row_placeholders)})")

        insert_sql = (
            f"INSERT INTO {table_name} ({', '.join(col_names)}) "
            f"VALUES {', '.join(value_rows)} "
            f"ON CONFLICT ({pk}) DO NOTHING"
        )

        try:
            with pg_engine.connect() as dst:
                dst.execute(text(insert_sql), bind_params)
                dst.commit()
            inserted += len(batch)
            retries = 0
            print(f"    {min(i + BATCH_SIZE, total)}/{total}")
        except Exception as e:
            retries += 1
            if retries > 8:
                print(f"  FAILED after 8 retries at row {i}: {e}")
                raise
            wait = min(2 ** retries, 30)
            print(f"    Error at row {i}, retrying in {wait}s... ({e})")
            time.sleep(wait)
            # Retry same batch
            continue

    print(f"  {table_name}: DONE ({inserted} rows inserted)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true",
                        help="Resume interrupted migration (skip existing rows)")
    parser.add_argument("--clear", action="store_true",
                        help="Clear all target tables before migrating")
    args = parser.parse_args()

    if args.resume and args.clear:
        print("ERROR: --resume and --clear are mutually exclusive")
        sys.exit(1)

    print(f"Source: SQLite @ {SQLITE_PATH}")
    print(f"Target: PostgreSQL @ {PG_URL.split('@')[1] if '@' in PG_URL else '***'}")
    print(f"Mode: {'resume' if args.resume else 'clear' if args.clear else 'fresh'}")
    print()

    # Ensure target tables exist
    from app.database import Base
    from app import models  # noqa
    Base.metadata.create_all(bind=pg_engine)
    print("Target tables verified.\n")

    if args.clear:
        print("Clearing all target tables...")
        with pg_engine.connect() as dst:
            for table in reversed(TABLES):
                dst.execute(text(f"DELETE FROM {table}"))
            dst.commit()
        print()

    for table in TABLES:
        migrate_table(table, resume=args.resume)

    # Reset sequences for auto-increment columns
    print("\nResetting sequences...")
    with pg_engine.connect() as dst:
        for table in ["allotments", "ref_courses", "ingestion_progress", "ingestion_errors"]:
            try:
                dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                ))
            except Exception:
                pass
        dst.commit()

    print("\nMigration complete!")


if __name__ == "__main__":
    main()
