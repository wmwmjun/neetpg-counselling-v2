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
from sqlalchemy.orm import Session, aliased
from sqlalchemy import or_, func

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
    round_: Optional[int],
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
    if round_ is not None:
        q = q.filter(Allotment.round == round_)
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

    # Final-only: for each rank, keep only the row(s) whose round equals the
    # highest round where the candidate still had a confirmed seat.
    # Uses a correlated subquery to avoid self-join ambiguity.
    if final_only:
        valid_seat = or_(
            Allotment.seat_outcome.is_(None),
            Allotment.seat_outcome.notin_(_INVALID_OUTCOMES),
        )
        # Alias to reference the same table inside the correlated subquery
        a2 = aliased(Allotment, name="a2_final")
        max_valid_round = (
            db.query(func.max(a2.round))
            .filter(
                a2.rank == Allotment.rank,
                a2.year == Allotment.year,
                a2.counselling_type == Allotment.counselling_type,
                or_(
                    a2.seat_outcome.is_(None),
                    a2.seat_outcome.notin_(_INVALID_OUTCOMES),
                ),
            )
            .correlate(Allotment)
            .scalar_subquery()
        )
        q = q.filter(valid_seat, Allotment.round == max_valid_round)

    # Sort: primary column, secondary always round ASC so same-rank rows
    # appear in chronological order (R1 → R2 → R3 …).
    # Tertiary by id for stable pagination.
    sort_col_map = {
        "rank": Allotment.rank,
        "institute_name": Allotment.institute_name,
        "course_norm": Allotment.course_norm,
        "sno": Allotment.sno,
    }
    col = sort_col_map.get(sort_by, Allotment.rank)
    if sort_order == "desc":
        q = q.order_by(col.desc().nullslast(), Allotment.round.asc(), Allotment.id.asc())
    else:
        q = q.order_by(col.asc().nullsfirst(), Allotment.round.asc(), Allotment.id.asc())

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
