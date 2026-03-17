#!/usr/bin/env python3
"""
Migrate all data from local SQLite to remote PostgreSQL (Supabase).

Usage (from backend/ directory):
    DATABASE_URL='postgresql+psycopg2://...' python3 -m scripts.migrate_sqlite_to_pg

Requires:
  - Local SQLite database at data/neetpg.db (default) or set SQLITE_PATH env var
  - DATABASE_URL env var pointing to PostgreSQL (Supabase)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

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

pg_engine = create_engine(PG_URL)

# Tables to migrate (in order to respect foreign key deps)
TABLES = [
    "institutes",
    "institute_mapping",
    "allotments",
    "ref_courses",
    "ingestion_progress",
    "ingestion_errors",
]

BATCH_SIZE = 500


def migrate_table(table_name: str):
    """Copy all rows from SQLite table to PostgreSQL."""
    # Check if table exists in SQLite
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

    print(f"  {table_name}: {len(rows)} rows to migrate...")

    with pg_engine.connect() as dst:
        # Clear existing data
        dst.execute(text(f"DELETE FROM {table_name}"))

        # Insert in batches
        placeholders = ", ".join(f":{c}" for c in col_names)
        insert_sql = f"INSERT INTO {table_name} ({', '.join(col_names)}) VALUES ({placeholders})"

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            params = [dict(zip(col_names, row)) for row in batch]
            dst.execute(text(insert_sql), params)
            print(f"    {min(i + BATCH_SIZE, len(rows))}/{len(rows)}")

        dst.commit()

    print(f"  {table_name}: DONE ({len(rows)} rows)")


def main():
    print(f"Source: SQLite @ {SQLITE_PATH}")
    print(f"Target: PostgreSQL @ {PG_URL.split('@')[1] if '@' in PG_URL else '***'}")
    print()

    # Ensure target tables exist
    from app.database import Base
    from app import models  # noqa
    Base.metadata.create_all(bind=pg_engine)
    print("Target tables verified.\n")

    for table in TABLES:
        migrate_table(table)

    print("\nMigration complete!")


if __name__ == "__main__":
    main()
