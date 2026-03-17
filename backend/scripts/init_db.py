#!/usr/bin/env python3
"""
Initialize the database (create all tables) and run lightweight column migrations.
Run from backend/ directory:
    python -m scripts.init_db
"""
import sys
import os

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from app.database import engine, Base
from app import models  # noqa: F401 – ensures models are registered


# New columns added after the initial schema — each entry is (column_name, DDL_type)
_NEW_ALLOTMENT_COLS = [
    ("r1_status",      "VARCHAR(128)"),
    ("seat_outcome",   "VARCHAR(16)"),
    ("option_code",    "VARCHAR(64)"),
    ("institute_city",    "VARCHAR(128)"),
    ("institute_pincode", "VARCHAR(10)"),
]


def _migrate_allotments(conn):
    """
    Add any missing columns to the allotments table.
    Uses SQLAlchemy inspector (works with both SQLite and PostgreSQL).
    This function is idempotent — safe to run multiple times.
    """
    inspector = inspect(engine)
    existing = {col["name"].lower() for col in inspector.get_columns("allotments")}
    for col_name, col_type in _NEW_ALLOTMENT_COLS:
        if col_name.lower() not in existing:
            conn.execute(
                text(f"ALTER TABLE allotments ADD COLUMN {col_name} {col_type}")
            )
            print(f"  ✓ Migration: added column allotments.{col_name}")


def main():
    print("Creating / verifying database tables...")
    Base.metadata.create_all(bind=engine)

    print("Running column migrations...")
    with engine.connect() as conn:
        _migrate_allotments(conn)
        conn.commit()

    print("Done. Tables:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")


if __name__ == "__main__":
    main()
