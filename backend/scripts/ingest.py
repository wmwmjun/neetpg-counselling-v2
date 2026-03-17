#!/usr/bin/env python3
"""
CLI ingestion script.

Usage examples:

  # Full ingestion (AIQ 2025 Round 1)
  python -m scripts.ingest \
      --pdf data/pdfs/AIQ_2025_R1.pdf \
      --year 2025 \
      --type AIQ \
      --round 1

  # Test mode: first 10 pages only
  python -m scripts.ingest \
      --pdf data/pdfs/AIQ_2025_R1.pdf \
      --year 2025 --type AIQ --round 1 \
      --test-pages 10

  # State counselling
  python -m scripts.ingest \
      --pdf data/pdfs/KA_2025_R1.pdf \
      --year 2025 --type STATE --state Karnataka --round 1

  # Round 2 ingestion (12-column PDF with combined R1+R2 data)
  python -m scripts.ingest \
      --pdf data/pdfs/AIQ_2025_R2.pdf \
      --year 2025 --type AIQ --round 2

  # Force re-ingest (ignore existing progress)
  python -m scripts.ingest ... --force
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.database import SessionLocal, engine, Base
from app import models  # noqa
from ingestion.config import DatasetConfig
from ingestion.pipeline import run_ingestion, run_round2_ingestion, run_round3_ingestion


def parse_args():
    p = argparse.ArgumentParser(description="NEET-PG Ingestion Pipeline")
    p.add_argument("--pdf", required=True, help="Path to the PDF file")
    p.add_argument("--year", type=int, required=True, help="Year (e.g. 2025)")
    p.add_argument("--type", dest="counselling_type", required=True,
                   choices=["AIQ", "STATE"], help="Counselling type")
    p.add_argument("--round", type=int, required=True, help="Round number (1–4)")
    p.add_argument("--state", dest="counselling_state", default=None,
                   help="State name (required for STATE counselling)")
    p.add_argument("--start-page", type=int, default=2,
                   help="First page to parse (default: 2, skip legend)")
    p.add_argument("--end-page", type=int, default=None,
                   help="Last page to parse (default: last page)")
    p.add_argument("--test-pages", type=int, default=None,
                   help="Process only N pages (test mode)")
    p.add_argument("--force", action="store_true",
                   help="Force re-ingestion even if already done")
    return p.parse_args()


def main():
    args = parse_args()

    cfg = DatasetConfig(
        year=args.year,
        counselling_type=args.counselling_type,
        counselling_state=args.counselling_state,
        round=args.round,
        pdf_path=args.pdf,
        start_page=args.start_page,
        end_page=args.end_page,
        test_mode_pages=args.test_pages,
    )

    try:
        cfg.validate()
    except AssertionError as e:
        print(f"Config validation error: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if args.force:
            from app.models import IngestionProgress
            existing = db.query(IngestionProgress).filter_by(
                dataset_key=cfg.dataset_key()
            ).first()
            if existing:
                db.delete(existing)
                db.commit()
                print(f"Cleared existing progress for {cfg.dataset_key()}")

        if args.round == 2:
            summary = run_round2_ingestion(cfg, db)
        elif args.round == 3:
            summary = run_round3_ingestion(cfg, db)
        else:
            # Round 1 and Round 4 (Stray Vacancy) share the same 8-column format
            summary = run_ingestion(cfg, db)
        print("\nIngestion summary:")
        for k, v in summary.items():
            print(f"  {k}: {v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
