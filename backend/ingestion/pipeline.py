"""
Ingestion pipeline.
Features:
  - Resume-safe (fingerprint-based deduplication + progress tracking)
  - Page-range test mode
  - Per-row error logging
  - Progress logging every N rows
"""
from __future__ import annotations
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.database import DATABASE_URL

# Use the correct dialect insert for upsert/on_conflict_do_nothing
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy.dialects.sqlite import insert as dialect_insert
else:
    from sqlalchemy.dialects.postgresql import insert as dialect_insert

from .config import DatasetConfig
from .normalizers import (
    normalize_quota,
    normalize_category,
    extract_state_from_institute,
    extract_city_from_institute,
    extract_pincode_from_institute,
    clean_institute_name,
    normalize_course,
    split_course_degree_specialty,
)
from .pdf_parser import (
    parse_pdf,
    COL_SNO, COL_RANK, COL_QUOTA, COL_INSTITUTE,
    COL_COURSE, COL_ALLOTTED_CAT, COL_CANDIDATE_CAT, COL_REMARKS,
    parse_round2_pdf,
    R2_COL_RANK,
    R2_COL_R1_QUOTA, R2_COL_R1_INSTITUTE, R2_COL_R1_COURSE, R2_COL_R1_STATUS,
    R2_COL_R2_QUOTA, R2_COL_R2_INSTITUTE, R2_COL_R2_COURSE,
    R2_COL_R2_ALLOTTED_CAT, R2_COL_R2_CANDIDATE_CAT,
    R2_COL_R2_OPTION_NO, R2_COL_R2_REMARKS,
    parse_round3_pdf,
    R3_COL_RANK,
    R3_COL_R1_QUOTA, R3_COL_R1_INSTITUTE, R3_COL_R1_COURSE, R3_COL_R1_REMARKS,
    R3_COL_R2_QUOTA, R3_COL_R2_INSTITUTE, R3_COL_R2_COURSE, R3_COL_R2_REMARKS,
    R3_COL_R3_QUOTA, R3_COL_R3_INSTITUTE, R3_COL_R3_COURSE,
    R3_COL_R3_ALLOTTED_CAT, R3_COL_R3_CANDIDATE_CAT,
    R3_COL_R3_OPTION_NO, R3_COL_R3_REMARKS,
)

logger = logging.getLogger(__name__)

LOG_EVERY = 100   # log progress every N rows


def _fingerprint(sno, rank, quota_raw, institute_raw, course_raw, allotted_cat_raw,
                  year=None, round_num=None) -> str:
    """SHA-256 fingerprint for deduplication.

    year and round_num are included in the hash to prevent collisions
    across different years/rounds (especially for RETAINED R2/R3 rows
    where effective fields are all None).
    """
    parts = "|".join(str(v or "") for v in [
        year, round_num, sno, rank, quota_raw, institute_raw, course_raw, allotted_cat_raw
    ])
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:40]


def _safe_int(val: Optional[str]) -> Optional[int]:
    if not val:
        return None
    try:
        return int(val.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return None


def run_ingestion(cfg: DatasetConfig, db: Session) -> dict:
    """
    Run the full ingestion for one dataset.

    Returns a summary dict with counts.
    """
    cfg.validate()

    from app.models import Allotment, IngestionError, IngestionProgress, RefCourse

    dataset_key = cfg.dataset_key()
    logger.info("Starting ingestion for dataset_key=%s", dataset_key)

    # -----------------------------------------------------------------------
    # Load or create progress record
    # -----------------------------------------------------------------------
    progress = db.query(IngestionProgress).filter_by(dataset_key=dataset_key).first()
    if progress is None:
        progress = IngestionProgress(
            dataset_key=dataset_key,
            last_page_completed=0,
            total_rows_inserted=0,
            total_rows_skipped=0,
            status="in_progress",
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    elif progress.status == "done":
        logger.info("Dataset %s already fully ingested. Use --force to re-run.", dataset_key)
        return {
            "status": "already_done",
            "rows_inserted": progress.total_rows_inserted,
            "rows_skipped": progress.total_rows_skipped,
        }

    resume_from_page = progress.last_page_completed + 1
    logger.info("Resuming from page %d", resume_from_page)

    # -----------------------------------------------------------------------
    # Determine page range
    # -----------------------------------------------------------------------
    import pdfplumber
    with pdfplumber.open(cfg.pdf_path) as pdf:
        total_pages = len(pdf.pages)

    effective_end = cfg.effective_end_page(total_pages)
    effective_start = max(cfg.start_page, resume_from_page)

    if effective_start > effective_end:
        logger.info("All pages already processed.")
        progress.status = "done"
        db.commit()
        return {"status": "already_done"}

    logger.info(
        "Processing pages %d–%d (total PDF pages: %d)",
        effective_start, effective_end, total_pages,
    )

    # -----------------------------------------------------------------------
    # Main ingestion loop
    # -----------------------------------------------------------------------
    rows_inserted = 0
    rows_skipped = 0
    rows_errored = 0
    current_page = effective_start

    for page_num, row in parse_pdf(cfg.pdf_path, effective_start, effective_end):

        # Track page transitions for resume checkpointing
        if page_num != current_page:
            # Commit progress at page boundary
            progress.last_page_completed = current_page
            progress.total_rows_inserted = progress.total_rows_inserted + rows_inserted
            progress.total_rows_skipped = progress.total_rows_skipped + rows_skipped
            progress.updated_at = datetime.utcnow()
            db.commit()
            current_page = page_num
            logger.debug("Checkpoint: page %d done.", current_page)

        try:
            record = _process_row(row, page_num, cfg)
            if record is None:
                rows_skipped += 1
                continue

            # Upsert via fingerprint uniqueness.
            # Use on_conflict_do_nothing() without index_elements so SQLite
            # generates INSERT OR IGNORE, catching ALL constraint violations
            # (the composite UNIQUE has NULL counselling_state which breaks
            # explicit ON CONFLICT targeting in SQLite).
            stmt = (
                dialect_insert(Allotment)
                .values(**record)
                .on_conflict_do_nothing()
            )
            result = db.execute(stmt)
            if result.rowcount == 0:
                rows_skipped += 1
            else:
                rows_inserted += 1

            if (rows_inserted + rows_skipped) % LOG_EVERY == 0:
                logger.info(
                    "Page %d | inserted=%d skipped=%d errored=%d",
                    page_num, rows_inserted, rows_skipped, rows_errored,
                )

        except Exception as exc:
            rows_errored += 1
            logger.warning("Page %d | row error: %s | row=%s", page_num, exc, row)
            err = IngestionError(
                year=cfg.year,
                counselling_type=cfg.counselling_type,
                counselling_state=cfg.counselling_state,
                round=cfg.round,
                page_num=page_num,
                row_data=json.dumps(row),
                error_msg=str(exc),
            )
            db.add(err)

    # Final commit
    progress.last_page_completed = effective_end
    progress.total_rows_inserted += rows_inserted
    progress.total_rows_skipped += rows_skipped
    progress.status = "done" if effective_end == total_pages else "in_progress"
    progress.updated_at = datetime.utcnow()
    db.commit()

    # -----------------------------------------------------------------------
    # Populate ref_courses from distinct course_norm
    # -----------------------------------------------------------------------
    _upsert_ref_courses(db)

    summary = {
        "status": progress.status,
        "pages_processed": effective_end - effective_start + 1,
        "rows_inserted": rows_inserted,
        "rows_skipped": rows_skipped,
        "rows_errored": rows_errored,
    }
    logger.info("Ingestion complete: %s", summary)
    return summary


def _process_row(
    row: list,
    page_num: int,
    cfg: DatasetConfig,
) -> Optional[dict]:
    """
    Parse and normalise a single raw row.
    Returns a dict ready for DB insertion, or None if the row should be skipped.
    """
    sno_raw = row[COL_SNO]
    rank_raw = row[COL_RANK]
    quota_raw = row[COL_QUOTA]
    institute_raw = row[COL_INSTITUTE]
    course_raw = row[COL_COURSE]
    allotted_cat_raw = row[COL_ALLOTTED_CAT]
    candidate_cat_raw = row[COL_CANDIDATE_CAT]
    remarks_raw = row[COL_REMARKS]

    sno = _safe_int(sno_raw)
    rank = _safe_int(rank_raw)

    # Skip rows with no rank (e.g. header echoes or blank rows)
    if rank is None:
        return None

    # Quota normalisation
    quota_norm, quota_known = normalize_quota(quota_raw)
    if not quota_known:
        logger.warning("Unknown quota '%s' on page %d", quota_raw, page_num)

    # Category normalisation
    allotted_cat_norm, cat_known = normalize_category(allotted_cat_raw)
    if not cat_known:
        logger.warning(
            "Unknown allotted_category '%s' on page %d", allotted_cat_raw, page_num
        )

    # Institute cleaning & state extraction
    institute_name = clean_institute_name(institute_raw)
    institute_city = extract_city_from_institute(institute_raw)
    institute_pincode = extract_pincode_from_institute(institute_raw)
    state = extract_state_from_institute(institute_raw)

    # Course normalisation
    course_norm = normalize_course(course_raw)

    # Fingerprint
    fp = _fingerprint(sno, rank, quota_raw, institute_raw, course_raw, allotted_cat_raw,
                      year=cfg.year, round_num=cfg.round)

    return {
        "year": cfg.year,
        "counselling_type": cfg.counselling_type,
        "counselling_state": cfg.counselling_state,
        "round": cfg.round,
        "sno": sno,
        "rank": rank,
        "quota_raw": quota_raw,
        "quota_norm": quota_norm,
        "institute_raw": institute_raw,
        "institute_name": institute_name,
        "institute_city": institute_city,
        "institute_pincode": institute_pincode,
        "state": state,
        "course_raw": course_raw,
        "course_norm": course_norm,
        "allotted_category_raw": allotted_cat_raw,
        "allotted_category_norm": allotted_cat_norm,
        "candidate_category_raw": candidate_cat_raw,
        "remarks": remarks_raw,
        "source_page": page_num,
        "source_row_fingerprint": fp,
    }


# ---------------------------------------------------------------------------
# Round 2 helpers
# ---------------------------------------------------------------------------

def _is_dash(val: Optional[str]) -> bool:
    """Return True if value is empty / a dash placeholder from the PDF."""
    return not val or val.strip() in ("-", "—", "–", "NA", "N/A", "")


def _compute_seat_outcome(r1_status_raw: Optional[str], r2_remarks_raw: Optional[str]) -> str:
    """
    Derive the seat outcome for a Round-2 row from the R1 status and R2 remarks.

    Returns one of:
        RETAINED       – kept the R1 seat, no upgrade happened
        UPGRADED       – upgraded to a new seat in R2
        LOST           – R1 seat released, no R2 seat secured
        FRESH          – no prior R1 seat (or R1 seat surrendered/not-reported),
                         new seat allotted in R2
        NOT_ALLOTTED   – explicitly not allotted in R2
        UNKNOWN        – does not match any known pattern
    """
    r1 = (r1_status_raw or "").upper().strip()
    r2 = (r2_remarks_raw or "").upper().strip()

    # -----------------------------------------------------------------------
    # R1 = Reported
    # -----------------------------------------------------------------------
    if "REPORTED" in r1 and "NOT REPORTED" not in r1:
        if "UPGRADED" in r2:
            return "UPGRADED"
        # "Did not opt for Upgradation" / "No Upgradation" / "Did not fill up fresh choices"
        if (
            "DID NOT OPT" in r2
            or "NO UPGRADATION" in r2
            or "DID NOT FILL" in r2
        ):
            return "RETAINED"
        # Catch-all for any other Reported + non-upgraded remarks
        return "RETAINED"

    # -----------------------------------------------------------------------
    # R1 = Not Reported
    # -----------------------------------------------------------------------
    if "NOT REPORTED" in r1:
        if "FRESH ALLOT" in r2:           # "Fresh Allotted in 2nd Round"
            return "FRESH"
        if "NOT ALLOTTED" in r2:
            return "NOT_ALLOTTED"
        if "DID NOT FILL" in r2:
            return "LOST"
        return "LOST"

    # -----------------------------------------------------------------------
    # R1 = Seat Surrendered
    # -----------------------------------------------------------------------
    if "SURRENDERED" in r1:
        if "FRESH ALLOT" in r2:
            return "FRESH"
        if "NOT ALLOTTED" in r2:
            return "NOT_ALLOTTED"
        # Fallback: check R2 data presence later in the pipeline
        return "LOST"

    # -----------------------------------------------------------------------
    # R1 is blank / dash  (candidate had no R1 allotment)
    # -----------------------------------------------------------------------
    if "FRESH ALLOT" in r2:
        return "FRESH"
    if "NOT ALLOTTED" in r2:
        return "NOT_ALLOTTED"

    return "UNKNOWN"


def _process_r2_row(
    row: list,
    page_num: int,
    cfg: "DatasetConfig",
) -> Optional[dict]:
    """
    Parse and normalise one Round-2 row (12 normalised columns).
    Returns a dict ready for DB insertion, or None to skip.

    Seat-outcome logic:
      RETAINED   → R2 allotment record inherits R1 institute/course/quota
      UPGRADED   → R2 allotment record uses R2 institute/course/quota
      FRESH      → R2 allotment record uses R2 institute/course/quota
      LOST / NOT_ALLOTTED / UNKNOWN → R2 record stored with null institute/course
    """
    rank_raw = row[R2_COL_RANK]
    rank = _safe_int(rank_raw)
    if rank is None:
        return None

    r1_quota_raw = row[R2_COL_R1_QUOTA]
    r1_institute_raw = row[R2_COL_R1_INSTITUTE]
    r1_course_raw = row[R2_COL_R1_COURSE]
    r1_status_raw = row[R2_COL_R1_STATUS]

    r2_quota_raw = row[R2_COL_R2_QUOTA]
    r2_institute_raw = row[R2_COL_R2_INSTITUTE]
    r2_course_raw = row[R2_COL_R2_COURSE]
    r2_allotted_cat_raw = row[R2_COL_R2_ALLOTTED_CAT]
    r2_candidate_cat_raw = row[R2_COL_R2_CANDIDATE_CAT]
    r2_option_no_raw = row[R2_COL_R2_OPTION_NO]
    r2_remarks_raw = row[R2_COL_R2_REMARKS]

    outcome = _compute_seat_outcome(r1_status_raw, r2_remarks_raw)

    # -----------------------------------------------------------------------
    # Choose which data to use for the R2 allotment record
    # -----------------------------------------------------------------------
    if outcome == "RETAINED":
        # Candidate kept R1 seat — use R1 institute / course / quota for the R2 row
        eff_quota_raw = r1_quota_raw
        eff_institute_raw = r1_institute_raw
        eff_course_raw = r1_course_raw
        eff_allotted_cat_raw = None   # not present in R2 col for retained rows
        eff_candidate_cat_raw = None
    elif outcome in ("UPGRADED", "FRESH"):
        # New seat in R2
        eff_quota_raw = r2_quota_raw if not _is_dash(r2_quota_raw) else None
        eff_institute_raw = r2_institute_raw if not _is_dash(r2_institute_raw) else None
        eff_course_raw = r2_course_raw if not _is_dash(r2_course_raw) else None
        eff_allotted_cat_raw = r2_allotted_cat_raw if not _is_dash(r2_allotted_cat_raw) else None
        eff_candidate_cat_raw = r2_candidate_cat_raw if not _is_dash(r2_candidate_cat_raw) else None
    else:
        # LOST / NOT_ALLOTTED / UNKNOWN — no effective seat
        eff_quota_raw = None
        eff_institute_raw = None
        eff_course_raw = None
        eff_allotted_cat_raw = None
        eff_candidate_cat_raw = None

    # Normalise the effective fields
    quota_norm, quota_known = normalize_quota(eff_quota_raw) if eff_quota_raw else ("UNKNOWN", False)
    if eff_quota_raw and not quota_known:
        logger.warning("Unknown quota '%s' on page %d", eff_quota_raw, page_num)

    allotted_cat_norm, cat_known = (
        normalize_category(eff_allotted_cat_raw) if eff_allotted_cat_raw else ("UNKNOWN", False)
    )
    if eff_allotted_cat_raw and not cat_known:
        logger.warning("Unknown allotted_category '%s' on page %d", eff_allotted_cat_raw, page_num)

    institute_name = clean_institute_name(eff_institute_raw)
    institute_city = extract_city_from_institute(eff_institute_raw)
    institute_pincode = extract_pincode_from_institute(eff_institute_raw)
    state = extract_state_from_institute(eff_institute_raw)
    course_norm = normalize_course(eff_course_raw) if eff_course_raw else ""

    # Fingerprint — use r2_remarks to distinguish from any R1 row with same rank
    fp = _fingerprint(
        None,                  # no sno in R2
        rank,
        eff_quota_raw,
        eff_institute_raw,
        eff_course_raw,
        r2_remarks_raw,        # substitute for allotted_cat to keep uniqueness
        year=cfg.year,
        round_num=cfg.round,
    )

    return {
        "year": cfg.year,
        "counselling_type": cfg.counselling_type,
        "counselling_state": cfg.counselling_state,
        "round": cfg.round,
        "sno": None,
        "rank": rank,
        "quota_raw": eff_quota_raw,
        "quota_norm": quota_norm if eff_quota_raw else None,
        "institute_raw": eff_institute_raw,
        "institute_name": institute_name,
        "institute_city": institute_city,
        "institute_pincode": institute_pincode,
        "state": state,
        "course_raw": eff_course_raw,
        "course_norm": course_norm,
        "allotted_category_raw": eff_allotted_cat_raw,
        "allotted_category_norm": allotted_cat_norm if eff_allotted_cat_raw else None,
        "candidate_category_raw": eff_candidate_cat_raw,
        "remarks": r2_remarks_raw,
        "source_page": page_num,
        "source_row_fingerprint": fp,
        # Round-2 specific
        "r1_status": r1_status_raw,
        "seat_outcome": outcome,
        "option_code": r2_option_no_raw if not _is_dash(r2_option_no_raw) else None,
    }


def run_round2_ingestion(cfg: "DatasetConfig", db: Session) -> dict:
    """
    Ingest a Round-2 PDF.

    Each 12-column row in the PDF represents one candidate's combined R1+R2 outcome.
    One Allotment record (round=2) is written per row using the effective seat data
    determined by the R1 status × R2 remarks business logic.
    """
    cfg.validate()

    from app.models import Allotment, IngestionError, IngestionProgress, RefCourse

    dataset_key = cfg.dataset_key()
    logger.info("Starting Round-2 ingestion for dataset_key=%s", dataset_key)

    progress = db.query(IngestionProgress).filter_by(dataset_key=dataset_key).first()
    if progress is None:
        progress = IngestionProgress(
            dataset_key=dataset_key,
            last_page_completed=0,
            total_rows_inserted=0,
            total_rows_skipped=0,
            status="in_progress",
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    elif progress.status == "done":
        logger.info("Dataset %s already fully ingested. Use --force to re-run.", dataset_key)
        return {
            "status": "already_done",
            "rows_inserted": progress.total_rows_inserted,
            "rows_skipped": progress.total_rows_skipped,
        }

    resume_from_page = progress.last_page_completed + 1

    import pdfplumber
    with pdfplumber.open(cfg.pdf_path) as pdf:
        total_pages = len(pdf.pages)

    effective_end = cfg.effective_end_page(total_pages)
    effective_start = max(cfg.start_page, resume_from_page)

    if effective_start > effective_end:
        logger.info("All pages already processed.")
        progress.status = "done"
        db.commit()
        return {"status": "already_done"}

    logger.info(
        "Round-2: processing pages %d–%d (total PDF pages: %d)",
        effective_start, effective_end, total_pages,
    )

    rows_inserted = 0
    rows_skipped = 0
    rows_errored = 0
    current_page = effective_start

    for page_num, row in parse_round2_pdf(cfg.pdf_path, effective_start, effective_end):
        if page_num != current_page:
            progress.last_page_completed = current_page
            progress.total_rows_inserted = progress.total_rows_inserted + rows_inserted
            progress.total_rows_skipped = progress.total_rows_skipped + rows_skipped
            progress.updated_at = datetime.utcnow()
            db.commit()
            current_page = page_num

        try:
            record = _process_r2_row(row, page_num, cfg)
            if record is None:
                rows_skipped += 1
                continue

            stmt = (
                dialect_insert(Allotment)
                .values(**record)
                .on_conflict_do_nothing()
            )
            result = db.execute(stmt)
            if result.rowcount == 0:
                rows_skipped += 1
            else:
                rows_inserted += 1

            if (rows_inserted + rows_skipped) % LOG_EVERY == 0:
                logger.info(
                    "Page %d | inserted=%d skipped=%d errored=%d",
                    page_num, rows_inserted, rows_skipped, rows_errored,
                )

        except Exception as exc:
            rows_errored += 1
            logger.warning("Page %d | row error: %s | row=%s", page_num, exc, row)
            err = IngestionError(
                year=cfg.year,
                counselling_type=cfg.counselling_type,
                counselling_state=cfg.counselling_state,
                round=cfg.round,
                page_num=page_num,
                row_data=str(row),
                error_msg=str(exc),
            )
            db.add(err)

    progress.last_page_completed = effective_end
    progress.total_rows_inserted += rows_inserted
    progress.total_rows_skipped += rows_skipped
    progress.status = "done" if effective_end == total_pages else "in_progress"
    progress.updated_at = datetime.utcnow()
    db.commit()

    _upsert_ref_courses(db)
    _backfill_retained_categories(db, cfg)

    summary = {
        "status": progress.status,
        "pages_processed": effective_end - effective_start + 1,
        "rows_inserted": rows_inserted,
        "rows_skipped": rows_skipped,
        "rows_errored": rows_errored,
    }
    logger.info("Round-2 ingestion complete: %s", summary)
    return summary


def _backfill_retained_categories(db: Session, cfg: "DatasetConfig") -> None:
    """
    Fill in allotted_category_norm AND institute_pincode for RETAINED R2 rows
    by joining with R1 data. RETAINED candidates kept their R1 seat, so their
    R2 category and pincode should match the R1 allotment exactly.
    """
    from sqlalchemy import text as sa_text

    # Backfill category
    result = db.execute(sa_text("""
        UPDATE allotments
        SET allotted_category_norm = (
            SELECT r1.allotted_category_norm
            FROM allotments r1
            WHERE r1.round = 1
              AND r1.year = allotments.year
              AND r1.counselling_type = allotments.counselling_type
              AND r1.rank = allotments.rank
            LIMIT 1
        )
        WHERE round = 2
          AND year = :year
          AND counselling_type = :ct
          AND seat_outcome = 'RETAINED'
          AND allotted_category_norm IS NULL
    """), {"year": cfg.year, "ct": cfg.counselling_type})
    db.commit()
    if result.rowcount:
        logger.info("Backfilled %d RETAINED rows with category from R1", result.rowcount)

    # Backfill institute_pincode (R2 PDF R1_INSTITUTE column doesn't carry full address+pincode)
    result2 = db.execute(sa_text("""
        UPDATE allotments
        SET institute_pincode = (
            SELECT r1.institute_pincode
            FROM allotments r1
            WHERE r1.round = 1
              AND r1.year = allotments.year
              AND r1.counselling_type = allotments.counselling_type
              AND r1.rank = allotments.rank
            LIMIT 1
        )
        WHERE round = 2
          AND year = :year
          AND counselling_type = :ct
          AND seat_outcome = 'RETAINED'
          AND institute_pincode IS NULL
    """), {"year": cfg.year, "ct": cfg.counselling_type})
    db.commit()
    if result2.rowcount:
        logger.info("Backfilled %d RETAINED rows with institute_pincode from R1", result2.rowcount)

    # Backfill state (R2 PDF R1_INSTITUTE column is shorter, may not contain state info)
    result3 = db.execute(sa_text("""
        UPDATE allotments
        SET state = (
            SELECT r1.state
            FROM allotments r1
            WHERE r1.round = 1
              AND r1.year = allotments.year
              AND r1.counselling_type = allotments.counselling_type
              AND r1.rank = allotments.rank
            LIMIT 1
        )
        WHERE round = 2
          AND year = :year
          AND counselling_type = :ct
          AND seat_outcome = 'RETAINED'
          AND state IS NULL
    """), {"year": cfg.year, "ct": cfg.counselling_type})
    db.commit()
    if result3.rowcount:
        logger.info("Backfilled %d RETAINED rows with state from R1", result3.rowcount)

    # Backfill institute_city (R2 PDF R1_INSTITUTE column is shorter, may not contain city info)
    result4 = db.execute(sa_text("""
        UPDATE allotments
        SET institute_city = (
            SELECT r1.institute_city
            FROM allotments r1
            WHERE r1.round = 1
              AND r1.year = allotments.year
              AND r1.counselling_type = allotments.counselling_type
              AND r1.rank = allotments.rank
            LIMIT 1
        )
        WHERE round = 2
          AND year = :year
          AND counselling_type = :ct
          AND seat_outcome = 'RETAINED'
          AND institute_city IS NULL
    """), {"year": cfg.year, "ct": cfg.counselling_type})
    db.commit()
    if result4.rowcount:
        logger.info("Backfilled %d RETAINED rows with institute_city from R1", result4.rowcount)


# ---------------------------------------------------------------------------
# Round 3 helpers
# ---------------------------------------------------------------------------

def _compute_r3_seat_outcome(
    r1_remarks_raw: Optional[str],
    r2_remarks_raw: Optional[str],
    r3_remarks_raw: Optional[str],
    r3_has_data: bool,
    r2_has_data: bool,
) -> str:
    """
    Derive the seat outcome for a Round-3 row.

    Returns one of:
        UPGRADED       – got a new (better) seat in R3
        FRESH          – no prior seat, new allotment in R3
        RETAINED       – kept the seat from R1 or R2
        NOT_ALLOTTED   – no seat after R3
        UNKNOWN        – does not match any known pattern
    """
    r1 = (r1_remarks_raw or "").upper().strip()
    r3 = (r3_remarks_raw or "").upper().strip()

    # R3 has actual allotment data → new seat in R3
    if r3_has_data:
        if "UPGRADED" in r3:
            return "UPGRADED"
        if "FRESH ALLOT" in r3:
            return "FRESH"
        return "UPGRADED"   # default for any new R3 allotment

    # R3 is dashes — determine if candidate has a seat to retain

    # If R2 had actual change data → they had an R2 seat → retained
    if r2_has_data:
        return "RETAINED"

    # R2 also dashes — check R1 status
    if "REPORTED" in r1 and "NOT REPORTED" not in r1:
        # Had R1 seat and reported → retained through R2 and R3
        return "RETAINED"

    # R1 was Not Reported / Surrendered / dash — no seat
    if "NOT REPORTED" in r1 or "SURRENDERED" in r1:
        return "NOT_ALLOTTED"

    # R1 is also dash (no R1 allotment at all)
    if not r1 or r1 in ("-", "—", "–"):
        return "NOT_ALLOTTED"

    return "UNKNOWN"


def _process_r3_row(
    row: list,
    page_num: int,
    cfg: "DatasetConfig",
) -> Optional[dict]:
    """
    Parse and normalise one Round-3 row (16 normalised columns).
    Returns a dict ready for DB insertion, or None to skip.

    Seat-outcome logic:
      UPGRADED / FRESH → R3 allotment record uses R3 cols (full data)
      RETAINED         → stored with null effective fields, backfilled later
      NOT_ALLOTTED     → stored with null institute/course (won't appear in CR)
    """
    rank_raw = row[R3_COL_RANK]
    rank = _safe_int(rank_raw)
    if rank is None:
        return None

    r1_remarks_raw = row[R3_COL_R1_REMARKS]
    r2_remarks_raw = row[R3_COL_R2_REMARKS]
    r3_remarks_raw = row[R3_COL_R3_REMARKS]

    r3_has_data = not _is_dash(row[R3_COL_R3_INSTITUTE])
    r2_has_data = not _is_dash(row[R3_COL_R2_INSTITUTE])

    outcome = _compute_r3_seat_outcome(
        r1_remarks_raw, r2_remarks_raw, r3_remarks_raw,
        r3_has_data, r2_has_data,
    )

    # -----------------------------------------------------------------------
    # Choose effective data based on outcome
    # -----------------------------------------------------------------------
    if outcome in ("UPGRADED", "FRESH"):
        # New seat in R3 — use R3 columns (full data)
        eff_quota_raw = row[R3_COL_R3_QUOTA] if not _is_dash(row[R3_COL_R3_QUOTA]) else None
        eff_institute_raw = row[R3_COL_R3_INSTITUTE] if not _is_dash(row[R3_COL_R3_INSTITUTE]) else None
        eff_course_raw = row[R3_COL_R3_COURSE] if not _is_dash(row[R3_COL_R3_COURSE]) else None
        eff_allotted_cat_raw = row[R3_COL_R3_ALLOTTED_CAT] if not _is_dash(row[R3_COL_R3_ALLOTTED_CAT]) else None
        eff_candidate_cat_raw = row[R3_COL_R3_CANDIDATE_CAT] if not _is_dash(row[R3_COL_R3_CANDIDATE_CAT]) else None
    else:
        # RETAINED / NOT_ALLOTTED / UNKNOWN — set all effective data to None
        # RETAINED rows will be backfilled from prior round records later
        eff_quota_raw = None
        eff_institute_raw = None
        eff_course_raw = None
        eff_allotted_cat_raw = None
        eff_candidate_cat_raw = None

    # Normalise the effective fields
    quota_norm = None
    if eff_quota_raw:
        quota_norm, quota_known = normalize_quota(eff_quota_raw)
        if not quota_known:
            logger.warning("Unknown quota '%s' on page %d", eff_quota_raw, page_num)

    allotted_cat_norm = None
    if eff_allotted_cat_raw:
        allotted_cat_norm, cat_known = normalize_category(eff_allotted_cat_raw)
        if not cat_known:
            logger.warning("Unknown allotted_category '%s' on page %d", eff_allotted_cat_raw, page_num)

    institute_name = clean_institute_name(eff_institute_raw) if eff_institute_raw else None
    institute_city = extract_city_from_institute(eff_institute_raw) if eff_institute_raw else None
    institute_pincode = extract_pincode_from_institute(eff_institute_raw) if eff_institute_raw else None
    state_val = extract_state_from_institute(eff_institute_raw) if eff_institute_raw else None
    course_norm = normalize_course(eff_course_raw) if eff_course_raw else None

    # Fingerprint — use r3_remarks + rank for uniqueness
    fp = _fingerprint(
        None, rank, eff_quota_raw, eff_institute_raw, eff_course_raw, r3_remarks_raw,
        year=cfg.year, round_num=cfg.round,
    )

    return {
        "year": cfg.year,
        "counselling_type": cfg.counselling_type,
        "counselling_state": cfg.counselling_state,
        "round": cfg.round,
        "sno": None,
        "rank": rank,
        "quota_raw": eff_quota_raw,
        "quota_norm": quota_norm,
        "institute_raw": eff_institute_raw,
        "institute_name": institute_name,
        "institute_city": institute_city,
        "institute_pincode": institute_pincode,
        "state": state_val,
        "course_raw": eff_course_raw,
        "course_norm": course_norm,
        "allotted_category_raw": eff_allotted_cat_raw,
        "allotted_category_norm": allotted_cat_norm,
        "candidate_category_raw": eff_candidate_cat_raw,
        "remarks": r3_remarks_raw,
        "source_page": page_num,
        "source_row_fingerprint": fp,
        # Round-3 specific
        "r1_status": r1_remarks_raw,
        "seat_outcome": outcome,
        "option_code": row[R3_COL_R3_OPTION_NO] if not _is_dash(row[R3_COL_R3_OPTION_NO]) else None,
    }


def run_round3_ingestion(cfg: "DatasetConfig", db: Session) -> dict:
    """
    Ingest a Round-3 PDF.

    Each 16-column row represents one candidate's combined R1+R2+R3 outcome.
    One Allotment record (round=3) is written per row using the effective seat data.
    RETAINED candidates are stored with null fields and backfilled from prior rounds.
    """
    cfg.validate()

    from app.models import Allotment, IngestionError, IngestionProgress

    dataset_key = cfg.dataset_key()
    logger.info("Starting Round-3 ingestion for dataset_key=%s", dataset_key)

    progress = db.query(IngestionProgress).filter_by(dataset_key=dataset_key).first()
    if progress is None:
        progress = IngestionProgress(
            dataset_key=dataset_key,
            last_page_completed=0,
            total_rows_inserted=0,
            total_rows_skipped=0,
            status="in_progress",
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    elif progress.status == "done":
        logger.info("Dataset %s already fully ingested. Use --force to re-run.", dataset_key)
        return {
            "status": "already_done",
            "rows_inserted": progress.total_rows_inserted,
            "rows_skipped": progress.total_rows_skipped,
        }

    resume_from_page = progress.last_page_completed + 1

    import pdfplumber
    with pdfplumber.open(cfg.pdf_path) as pdf:
        total_pages = len(pdf.pages)

    effective_end = cfg.effective_end_page(total_pages)
    effective_start = max(cfg.start_page, resume_from_page)

    if effective_start > effective_end:
        logger.info("All pages already processed.")
        progress.status = "done"
        db.commit()
        return {"status": "already_done"}

    logger.info(
        "Round-3: processing pages %d–%d (total PDF pages: %d)",
        effective_start, effective_end, total_pages,
    )

    rows_inserted = 0
    rows_skipped = 0
    rows_errored = 0
    current_page = effective_start

    for page_num, row in parse_round3_pdf(cfg.pdf_path, effective_start, effective_end):
        if page_num != current_page:
            progress.last_page_completed = current_page
            progress.total_rows_inserted = progress.total_rows_inserted + rows_inserted
            progress.total_rows_skipped = progress.total_rows_skipped + rows_skipped
            progress.updated_at = datetime.utcnow()
            db.commit()
            current_page = page_num

        try:
            record = _process_r3_row(row, page_num, cfg)
            if record is None:
                rows_skipped += 1
                continue

            stmt = (
                dialect_insert(Allotment)
                .values(**record)
                .on_conflict_do_nothing()
            )
            result = db.execute(stmt)
            if result.rowcount == 0:
                rows_skipped += 1
            else:
                rows_inserted += 1

            if (rows_inserted + rows_skipped) % LOG_EVERY == 0:
                logger.info(
                    "Page %d | inserted=%d skipped=%d errored=%d",
                    page_num, rows_inserted, rows_skipped, rows_errored,
                )

        except Exception as exc:
            rows_errored += 1
            logger.warning("Page %d | row error: %s | row=%s", page_num, exc, row)
            err = IngestionError(
                year=cfg.year,
                counselling_type=cfg.counselling_type,
                counselling_state=cfg.counselling_state,
                round=cfg.round,
                page_num=page_num,
                row_data=str(row),
                error_msg=str(exc),
            )
            db.add(err)

    progress.last_page_completed = effective_end
    progress.total_rows_inserted += rows_inserted
    progress.total_rows_skipped += rows_skipped
    progress.status = "done" if effective_end == total_pages else "in_progress"
    progress.updated_at = datetime.utcnow()
    db.commit()

    _upsert_ref_courses(db)
    _backfill_retained_from_prior_rounds(db, cfg, target_round=3)

    summary = {
        "status": progress.status,
        "pages_processed": effective_end - effective_start + 1,
        "rows_inserted": rows_inserted,
        "rows_skipped": rows_skipped,
        "rows_errored": rows_errored,
    }
    logger.info("Round-3 ingestion complete: %s", summary)
    return summary


def _backfill_retained_from_prior_rounds(
    db: Session,
    cfg: "DatasetConfig",
    target_round: int,
) -> None:
    """
    Fill in all effective fields for RETAINED rows in `target_round`
    by copying from the latest prior round record (round < target_round)
    that has non-null data for each field.

    This handles both R3 RETAINED (backfill from R2 or R1) and could be
    reused for future rounds.
    """
    from sqlalchemy import text as sa_text

    fields_to_backfill = [
        "institute_name", "institute_city", "institute_pincode", "state",
        "course_norm", "course_raw", "quota_norm", "quota_raw",
        "allotted_category_norm", "allotted_category_raw",
        "candidate_category_raw", "institute_raw",
    ]

    total_backfilled = 0
    for field in fields_to_backfill:
        result = db.execute(sa_text(f"""
            UPDATE allotments
            SET {field} = (
                SELECT r.{field}
                FROM allotments r
                WHERE r.rank = allotments.rank
                  AND r.year = allotments.year
                  AND r.counselling_type = allotments.counselling_type
                  AND r.round < :target_round
                  AND r.{field} IS NOT NULL
                  AND r.{field} != ''
                ORDER BY r.round DESC
                LIMIT 1
            )
            WHERE round = :target_round
              AND year = :year
              AND counselling_type = :ct
              AND seat_outcome = 'RETAINED'
              AND ({field} IS NULL OR {field} = '')
        """), {
            "target_round": target_round,
            "year": cfg.year,
            "ct": cfg.counselling_type,
        })
        if result.rowcount:
            logger.info(
                "Backfilled %d RETAINED R%d rows: %s from prior rounds",
                result.rowcount, target_round, field,
            )
            total_backfilled += result.rowcount

    db.commit()
    if total_backfilled:
        logger.info("Total R%d RETAINED backfills: %d field-updates", target_round, total_backfilled)


def _upsert_ref_courses(db: Session) -> None:
    """Populate/update ref_courses from distinct course_norm in allotments."""
    from app.models import Allotment, RefCourse

    existing = {r.course_norm for r in db.query(RefCourse.course_norm).all()}

    new_courses = (
        db.query(Allotment.course_norm)
        .filter(Allotment.course_norm.isnot(None))
        .filter(Allotment.course_norm != "")
        .distinct()
        .all()
    )

    added = 0
    for (course_norm,) in new_courses:
        if course_norm in existing:
            continue
        degree, specialty = split_course_degree_specialty(course_norm)
        db.add(RefCourse(
            course_norm=course_norm,
            degree=degree,
            specialty=specialty,
        ))
        existing.add(course_norm)
        added += 1

    if added:
        db.commit()
        logger.info("ref_courses: added %d new entries.", added)
