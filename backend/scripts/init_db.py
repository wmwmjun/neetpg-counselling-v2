#!/usr/bin/env python3
"""
Initialize the database (create all tables).
Run from backend/ directory:
    python -m scripts.init_db
"""
import sys
import os

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
from app import models  # noqa: F401 – ensures models are registered


def main():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")


if __name__ == "__main__":
    main()
