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
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .config import DatasetConfig
from .normalizers import (
    normalize_quota,
    normalize_category,
    extract_state_from_institute,
    clean_institute_name,
    normalize_course,
    split_course_degree_specialty,
)
from .pdf_parser import (
    parse_pdf,
    COL_SNO, COL_RANK, COL_QUOTA, COL_INSTITUTE,
    COL_COURSE, COL_ALLOTTED_CAT, COL_CANDIDATE_CAT, COL_REMARKS,
)

logger = logging.getLogger(__name__)

LOG_EVERY = 100   # log progress every N rows


def _fingerprint(sno, rank, quota_raw, institute_raw, course_raw, allotted_cat_raw) -> str:
    """SHA-256 fingerprint for deduplication."""
    parts = "|".join(str(v or "") for v in [
        sno, rank, quota_raw, institute_raw, course_raw, allotted_cat_raw
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

            # Upsert via fingerprint uniqueness constraint
            stmt = (
                sqlite_insert(Allotment)
                .values(**record)
                .on_conflict_do_nothing(
                    index_elements=[
                        "year", "counselling_type", "counselling_state",
                        "round", "source_row_fingerprint",
                    ]
                )
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
    state = extract_state_from_institute(institute_raw)

    # Course normalisation
    course_norm = normalize_course(course_raw)

    # Fingerprint
    fp = _fingerprint(sno, rank, quota_raw, institute_raw, course_raw, allotted_cat_raw)

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
