"""
GET /allotments        — paginated individual allotment records
GET /allotments/export — streaming CSV download (no row limit)
"""
from __future__ import annotations
import csv
import io
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from ..database import get_db
from ..models import Allotment
from ..schemas import AllotmentRow, AllotmentListResponse

router = APIRouter()

# seat_outcome values that mean the candidate does NOT have a confirmed seat
_INVALID_OUTCOMES = ["LOST", "NOT_ALLOTTED"]


# ---------------------------------------------------------------------------
# Shared query builder
# ---------------------------------------------------------------------------

def _build_query(
    db: Session,
    year: Optional[int],
    counselling_type: Optional[str],
    counselling_state: Optional[str],
    round: Optional[int],
    quota_norm: Optional[str],
    allotted_category_norm: Optional[str],
    state: Optional[str],
    course_norm: Optional[str],
    institute_name: Optional[str],
    rank_min: Optional[int],
    rank_max: Optional[int],
    search: Optional[str],
    final_only: bool,
    sort_by: str,
    sort_order: str,
):
    q = db.query(Allotment)

    if year is not None:
        q = q.filter(Allotment.year == year)
    if counselling_type:
        q = q.filter(Allotment.counselling_type == counselling_type)
    if counselling_state is not None:
        if counselling_state == "":
            q = q.filter(Allotment.counselling_state.is_(None))
        else:
            q = q.filter(Allotment.counselling_state == counselling_state)
    if round is not None:
        q = q.filter(Allotment.round == round)
    if quota_norm:
        q = q.filter(Allotment.quota_norm == quota_norm)
    if allotted_category_norm:
        q = q.filter(Allotment.allotted_category_norm == allotted_category_norm)
    if state:
        q = q.filter(Allotment.state == state)
    if course_norm:
        q = q.filter(Allotment.course_norm.ilike(f"%{course_norm}%"))
    if institute_name:
        q = q.filter(Allotment.institute_name.ilike(f"%{institute_name}%"))
    if rank_min is not None:
        q = q.filter(Allotment.rank >= rank_min)
    if rank_max is not None:
        q = q.filter(Allotment.rank <= rank_max)
    if search:
        term = f"%{search}%"
        q = q.filter(
            or_(
                Allotment.institute_name.ilike(term),
                Allotment.course_norm.ilike(term),
                Allotment.course_raw.ilike(term),
                Allotment.institute_raw.ilike(term),
            )
        )

    # Final-only: keep only the max-round confirmed-seat row per rank.
    # "Confirmed seat" = seat_outcome IS NULL (R1 rows) or not LOST/NOT_ALLOTTED.
    if final_only:
        valid_seat = or_(
            Allotment.seat_outcome.is_(None),
            Allotment.seat_outcome.notin_(_INVALID_OUTCOMES),
        )
        max_round_subq = (
            q.filter(valid_seat)
            .with_entities(
                Allotment.rank.label("f_rank"),
                func.max(Allotment.round).label("f_max_round"),
            )
            .group_by(Allotment.rank)
            .subquery("max_rounds")
        )
        q = q.filter(valid_seat).join(
            max_round_subq,
            and_(
                Allotment.rank == max_round_subq.c.f_rank,
                Allotment.round == max_round_subq.c.f_max_round,
            ),
        )

    # Sort: when sorting by rank, add round as secondary sort (always asc)
    # so rows with the same rank appear in chronological round order.
    sort_col_map = {
        "rank": Allotment.rank,
        "institute_name": Allotment.institute_name,
        "course_norm": Allotment.course_norm,
        "sno": Allotment.sno,
    }
    col = sort_col_map.get(sort_by, Allotment.rank)
    if sort_order == "desc":
        q = q.order_by(col.desc().nullslast(), Allotment.round.asc())
    else:
        q = q.order_by(col.asc().nullsfirst(), Allotment.round.asc())

    return q


# ---------------------------------------------------------------------------
# GET /allotments/export  — streaming CSV download
# ---------------------------------------------------------------------------

@router.get("/export")
def export_allotments_csv(
    year: Optional[int] = Query(None),
    counselling_type: Optional[str] = Query(None),
    counselling_state: Optional[str] = Query(None),
    round: Optional[int] = Query(None),
    quota_norm: Optional[str] = Query(None),
    allotted_category_norm: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    course_norm: Optional[str] = Query(None),
    institute_name: Optional[str] = Query(None),
    rank_min: Optional[int] = Query(None),
    rank_max: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    final_only: bool = Query(False),
    sort_by: str = Query("rank", enum=["rank", "institute_name", "course_norm", "sno"]),
    sort_order: str = Query("asc", enum=["asc", "desc"]),
    db: Session = Depends(get_db),
):
    """Export current filtered allotments as CSV (no row limit)."""
    q = _build_query(
        db, year, counselling_type, counselling_state, round,
        quota_norm, allotted_category_norm, state, course_norm, institute_name,
        rank_min, rank_max, search, final_only, sort_by, sort_order,
    )
    rows = q.all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Rank", "Round", "Institute", "City", "Pincode", "State",
            "Course", "Quota", "Category", "Outcome",
            "Year", "Counselling Type",
        ])
        yield buf.getvalue()

        for r in rows:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                r.rank if r.rank is not None else "",
                r.round,
                r.institute_name or "",
                r.institute_city or "",
                r.institute_pincode or "",
                r.state or "",
                r.course_norm or r.course_raw or "",
                r.quota_norm or "",
                r.allotted_category_norm or "",
                r.seat_outcome or "",
                r.year,
                r.counselling_type,
            ])
            yield buf.getvalue()

    ct = counselling_type or "AIQ"
    yr = year or "all"
    filename = f"neetpg_allotments_{ct}_{yr}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /allotments
# ---------------------------------------------------------------------------

@router.get("", response_model=AllotmentListResponse)
def get_allotments(
    year: Optional[int] = Query(None),
    counselling_type: Optional[str] = Query(None),
    counselling_state: Optional[str] = Query(None),
    round: Optional[int] = Query(None),
    quota_norm: Optional[str] = Query(None),
    allotted_category_norm: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    course_norm: Optional[str] = Query(None),
    institute_name: Optional[str] = Query(None),
    rank_min: Optional[int] = Query(None),
    rank_max: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    final_only: bool = Query(False),
    sort_by: str = Query("rank", enum=["rank", "institute_name", "course_norm", "sno"]),
    sort_order: str = Query("asc", enum=["asc", "desc"]),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = _build_query(
        db, year, counselling_type, counselling_state, round,
        quota_norm, allotted_category_norm, state, course_norm, institute_name,
        rank_min, rank_max, search, final_only, sort_by, sort_order,
    )

    total = q.count()
    pages = math.ceil(total / page_size) if page_size else 1
    records = q.offset((page - 1) * page_size).limit(page_size).all()

    return AllotmentListResponse(
        data=[AllotmentRow.model_validate(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
