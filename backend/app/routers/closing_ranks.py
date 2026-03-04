"""
Closing Rank endpoints.

GET /closing-ranks
  Returns grouped closing-rank rows (MAX(rank) per group).
  All filtering is server-side SQL.

GET /closing-ranks/{group_id}/allotments
  Returns all individual allotments that contribute to one closing-rank group.
  group_id is a URL-safe base64-encoded JSON of the group key.
"""
from __future__ import annotations
import base64
import json
import math
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ..database import get_db
from ..models import Allotment
from ..schemas import (
    ClosingRankRow,
    ClosingRankListResponse,
    DrillDownRow,
    DrillDownResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Group ID helpers
# ---------------------------------------------------------------------------

def _encode_group_id(
    year: int,
    counselling_type: str,
    counselling_state: Optional[str],
    round: int,
    institute_name: Optional[str],
    course_norm: Optional[str],
    quota_norm: Optional[str],
    allotted_category_norm: Optional[str],
) -> str:
    payload = {
        "y": year,
        "ct": counselling_type,
        "cs": counselling_state or "",
        "r": round,
        "i": institute_name or "",
        "c": course_norm or "",
        "q": quota_norm or "",
        "a": allotted_category_norm or "",
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_group_id(group_id: str) -> dict:
    padding = 4 - len(group_id) % 4
    if padding != 4:
        group_id += "=" * padding
    try:
        return json.loads(base64.urlsafe_b64decode(group_id).decode())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid group_id: {exc}") from exc


# ---------------------------------------------------------------------------
# Shared filter builder
# ---------------------------------------------------------------------------

def _build_filters(
    query,
    year: Optional[int],
    counselling_type: Optional[str],
    counselling_state: Optional[str],
    round: Optional[int],
    quota_norm: Optional[str],
    allotted_category_norm: Optional[str],
    state: Optional[str],
    course_norm: Optional[str],
    rank_min: Optional[int],
    rank_max: Optional[int],
    search: Optional[str],
):
    if year is not None:
        query = query.filter(Allotment.year == year)
    if counselling_type:
        query = query.filter(Allotment.counselling_type == counselling_type)
    if counselling_state is not None:
        if counselling_state == "":
            query = query.filter(Allotment.counselling_state.is_(None))
        else:
            query = query.filter(Allotment.counselling_state == counselling_state)
    if round is not None:
        query = query.filter(Allotment.round == round)
    if quota_norm:
        query = query.filter(Allotment.quota_norm == quota_norm)
    if allotted_category_norm:
        query = query.filter(Allotment.allotted_category_norm == allotted_category_norm)
    if state:
        query = query.filter(Allotment.state == state)
    if course_norm:
        query = query.filter(Allotment.course_norm.ilike(f"%{course_norm}%"))
    if rank_min is not None:
        query = query.filter(Allotment.rank >= rank_min)
    if rank_max is not None:
        query = query.filter(Allotment.rank <= rank_max)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Allotment.institute_name.ilike(term),
                Allotment.course_norm.ilike(term),
                Allotment.course_raw.ilike(term),
            )
        )
    return query


# ---------------------------------------------------------------------------
# GET /closing-ranks
# ---------------------------------------------------------------------------

@router.get("", response_model=ClosingRankListResponse)
def get_closing_ranks(
    # Dataset dimensions (default: AIQ 2025 R1)
    year: int = Query(2025),
    counselling_type: str = Query("AIQ"),
    counselling_state: Optional[str] = Query(None),
    round: int = Query(1),
    # Filters
    quota_norm: str = Query("AI", description="Default: AI quota"),
    allotted_category_norm: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    course_norm: Optional[str] = Query(None),
    rank_min: Optional[int] = Query(None),
    rank_max: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    # Sort
    sort_by: str = Query("institute_name", enum=["institute_name", "course_norm", "closing_rank"]),
    sort_order: str = Query("asc", enum=["asc", "desc"]),
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Return grouped closing-rank rows.
    Closing rank is computed dynamically as MAX(rank) per group.
    """
    # ---- Build grouped subquery ----
    group_cols = [
        Allotment.year,
        Allotment.counselling_type,
        Allotment.counselling_state,
        Allotment.round,
        Allotment.institute_name,
        Allotment.state,
        Allotment.course_norm,
        Allotment.quota_norm,
        Allotment.allotted_category_norm,
    ]

    base = db.query(
        *group_cols,
        func.max(Allotment.rank).label("closing_rank"),
        func.count(Allotment.id).label("allotment_count"),
    ).group_by(*group_cols)

    # Apply filters
    base = _build_filters(
        base, year, counselling_type, counselling_state, round,
        quota_norm, allotted_category_norm, state, course_norm,
        rank_min, rank_max, search,
    )

    # Sort
    sort_col_map = {
        "institute_name": Allotment.institute_name,
        "course_norm": Allotment.course_norm,
        "closing_rank": func.max(Allotment.rank),
    }
    sort_col = sort_col_map.get(sort_by, Allotment.institute_name)
    if sort_order == "desc":
        base = base.order_by(sort_col.desc().nullslast())
    else:
        base = base.order_by(sort_col.asc().nullsfirst())

    # Total count
    total = base.count()
    pages = math.ceil(total / page_size) if page_size else 1
    offset = (page - 1) * page_size

    rows = base.offset(offset).limit(page_size).all()

    data = [
        ClosingRankRow(
            group_id=_encode_group_id(
                r.year, r.counselling_type, r.counselling_state,
                r.round, r.institute_name, r.course_norm,
                r.quota_norm, r.allotted_category_norm,
            ),
            year=r.year,
            counselling_type=r.counselling_type,
            counselling_state=r.counselling_state,
            round=r.round,
            institute_name=r.institute_name,
            state=r.state,
            course_norm=r.course_norm,
            quota_norm=r.quota_norm,
            allotted_category_norm=r.allotted_category_norm,
            closing_rank=r.closing_rank,
            allotment_count=r.allotment_count,
        )
        for r in rows
    ]

    return ClosingRankListResponse(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# GET /closing-ranks/{group_id}/allotments
# ---------------------------------------------------------------------------

@router.get("/{group_id}/allotments", response_model=DrillDownResponse)
def get_group_allotments(
    group_id: str,
    db: Session = Depends(get_db),
):
    """
    Drill-down: return all individual allotments for one closing-rank group.
    group_id is a URL-safe base64-encoded key (returned by GET /closing-ranks).
    Sorted by rank ascending.
    """
    g = _decode_group_id(group_id)

    # Extract group key fields
    year = int(g["y"])
    counselling_type = g["ct"]
    counselling_state = g["cs"] or None
    round_ = int(g["r"])
    institute_name = g["i"] or None
    course_norm = g["c"] or None
    quota_norm = g["q"] or None
    allotted_category_norm = g["a"] or None

    def _eq_or_null(col, val):
        """Helper: filter col == val, or col IS NULL when val is None."""
        if val is None:
            return col.is_(None)
        return col == val

    q = (
        db.query(Allotment)
        .filter(
            Allotment.year == year,
            Allotment.counselling_type == counselling_type,
            _eq_or_null(Allotment.counselling_state, counselling_state),
            Allotment.round == round_,
            _eq_or_null(Allotment.institute_name, institute_name),
            _eq_or_null(Allotment.course_norm, course_norm),
            _eq_or_null(Allotment.quota_norm, quota_norm),
            _eq_or_null(Allotment.allotted_category_norm, allotted_category_norm),
        )
        .order_by(Allotment.rank.asc())
    )

    allotments = q.all()

    if not allotments:
        raise HTTPException(status_code=404, detail="No allotments found for this group.")

    closing_rank = max(a.rank for a in allotments if a.rank is not None)

    data = [
        DrillDownRow(
            rank=a.rank,
            sno=a.sno,
            round=a.round,
            state=a.state,
            institute_name=a.institute_name,
            course_norm=a.course_norm,
            quota_norm=a.quota_norm,
            allotted_category_norm=a.allotted_category_norm,
            candidate_category_raw=a.candidate_category_raw,
            remarks=a.remarks,
        )
        for a in allotments
    ]

    return DrillDownResponse(
        group_id=group_id,
        closing_rank=closing_rank,
        allotment_count=len(data),
        data=data,
    )
