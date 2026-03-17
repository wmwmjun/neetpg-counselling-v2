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
import csv
import io
import json
import math
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, text as sa_text, select as sa_select, literal_column

from ..database import get_db
from ..models import Allotment, Institute, RefCourse
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
    institute_pincode: Optional[str],
    course_norm: Optional[str],
    quota_norm: Optional[str],
    allotted_category_norm: Optional[str],
) -> str:
    # Note: institute_city is NOT part of the group key (only pincode is used for institute identity)
    payload = {
        "y": year,
        "ct": counselling_type,
        "cs": counselling_state or "",
        "r": round,
        "i": institute_name or "",
        "ip": institute_pincode or "",
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
    quota_norm: Optional[List[str]],
    allotted_category_norm: Optional[List[str]],
    state: Optional[List[str]],
    course_norm: Optional[List[str]],
    rank_min: Optional[int],
    rank_max: Optional[int],
    search: Optional[str],
    course_type: Optional[List[str]] = None,
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
    if quota_norm:
        query = query.filter(Allotment.quota_norm.in_(quota_norm))
    if allotted_category_norm:
        query = query.filter(Allotment.allotted_category_norm.in_(allotted_category_norm))
    if state:
        query = query.filter(Allotment.state.in_(state))
    if course_norm:
        if len(course_norm) == 1:
            query = query.filter(Allotment.course_norm.ilike(f"%{course_norm[0]}%"))
        else:
            query = query.filter(Allotment.course_norm.in_(course_norm))
    if course_type:
        # Filter by course_type via ref_courses lookup
        matching_courses = sa_select(RefCourse.course_norm).where(
            RefCourse.course_type.in_(course_type)
        ).scalar_subquery()
        query = query.filter(Allotment.course_norm.in_(matching_courses))
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
# Shared pivot query builder (used by both JSON and CSV endpoints)
# ---------------------------------------------------------------------------

def _build_pivot_query(
    db: Session,
    year: int,
    counselling_type: str,
    counselling_state: Optional[str],
    quota_norm: Optional[List[str]],
    allotted_category_norm: Optional[List[str]],
    state: Optional[List[str]],
    course_norm: Optional[List[str]],
    rank_min: Optional[int],
    rank_max: Optional[int],
    search: Optional[str],
    round_display: Optional[List[str]],
    my_rank: Optional[int],
    sort_by: str,
    sort_order: str,
    fee_min: Optional[int] = None,
    fee_max: Optional[int] = None,
    bond_min: Optional[int] = None,
    bond_max: Optional[int] = None,
    course_type: Optional[List[str]] = None,
):
    group_cols = [
        Allotment.year,
        Allotment.counselling_type,
        Allotment.counselling_state,
        Allotment.institute_name,
        Allotment.institute_pincode,
        Allotment.state,
        Allotment.course_norm,
        Allotment.quota_norm,
        Allotment.allotted_category_norm,
    ]
    r1_rank_expr = func.max(case((Allotment.round == 1, Allotment.rank), else_=None))
    r1_count_expr = func.count(case((Allotment.round == 1, Allotment.id), else_=None))
    r2_rank_expr = func.max(case((Allotment.round == 2, Allotment.rank), else_=None))
    r2_count_expr = func.count(case((Allotment.round == 2, Allotment.id), else_=None))
    r3_rank_expr = func.max(case((Allotment.round == 3, Allotment.rank), else_=None))
    r3_count_expr = func.count(case((Allotment.round == 3, Allotment.id), else_=None))
    r4_rank_expr = func.max(case((Allotment.round == 4, Allotment.rank), else_=None))
    r4_count_expr = func.count(case((Allotment.round == 4, Allotment.id), else_=None))

    # Correlated subqueries: pull data from institutes table via institute_mapping.
    _inst_sub = (
        "(SELECT i.{col} FROM institute_mapping m"
        " JOIN institutes i ON m.institute_code = i.institute_code"
        " WHERE m.db_institute_name = allotments.institute_name LIMIT 1)"
    )
    pdf_addr_expr = literal_column(_inst_sub.format(col="address")).label("institute_address")
    verified_addr_expr = literal_column(_inst_sub.format(col="display_name")).label("institute_address_verified")
    inst_fee_yr1 = literal_column(
        "(SELECT CAST(i.annual_fee AS REAL) FROM institute_mapping m"
        " JOIN institutes i ON m.institute_code = i.institute_code"
        " WHERE m.db_institute_name = allotments.institute_name LIMIT 1)"
    ).label("inst_fee_yr1")
    inst_fee_yr2 = literal_column(_inst_sub.format(col="fee_yr2")).label("inst_fee_yr2")
    inst_fee_yr3 = literal_column(_inst_sub.format(col="fee_yr3")).label("inst_fee_yr3")
    inst_stipend_yr1 = literal_column(_inst_sub.format(col="stipend_yr1")).label("inst_stipend_yr1")
    inst_stipend_yr2 = literal_column(_inst_sub.format(col="stipend_yr2")).label("inst_stipend_yr2")
    inst_stipend_yr3 = literal_column(_inst_sub.format(col="stipend_yr3")).label("inst_stipend_yr3")
    inst_bond_forfeit_expr = literal_column(_inst_sub.format(col="bond_forfeit")).label("inst_bond_forfeit")
    inst_university_expr = literal_column(_inst_sub.format(col="university")).label("inst_university")
    inst_bond_years_expr = literal_column(_inst_sub.format(col="bond_years")).label("inst_bond_years")
    inst_beds_expr = literal_column(_inst_sub.format(col="beds")).label("inst_beds")
    inst_matched_expr = literal_column(
        "(SELECT CASE WHEN m.match_confidence IN ('EXACT','FUZZY') THEN 1 ELSE 0 END"
        " FROM institute_mapping m"
        " WHERE m.db_institute_name = allotments.institute_name LIMIT 1)"
    ).label("inst_matched")
    # Fallback pincode: use institute pincode when allotment pincode is missing
    inst_pincode_expr = literal_column(
        "COALESCE(allotments.institute_pincode, "
        + _inst_sub.format(col="pincode")
        + ")"
    ).label("pincode_resolved")

    base = db.query(
        *group_cols,
        func.min(Allotment.institute_city).label("institute_city"),
        r1_rank_expr.label("r1_closing_rank"),
        r1_count_expr.label("r1_allotment_count"),
        r2_rank_expr.label("r2_closing_rank"),
        r2_count_expr.label("r2_allotment_count"),
        r3_rank_expr.label("r3_closing_rank"),
        r3_count_expr.label("r3_allotment_count"),
        r4_rank_expr.label("r4_closing_rank"),
        r4_count_expr.label("r4_allotment_count"),
        pdf_addr_expr, verified_addr_expr,
        inst_fee_yr1, inst_fee_yr2, inst_fee_yr3,
        inst_stipend_yr1, inst_stipend_yr2, inst_stipend_yr3,
        inst_bond_forfeit_expr, inst_bond_years_expr, inst_beds_expr,
        inst_university_expr,
        inst_matched_expr,
        inst_pincode_expr,
    ).group_by(*group_cols)

    base = base.filter(
        Allotment.institute_name.isnot(None),
        Allotment.allotted_category_norm.isnot(None),
    )
    base = _build_filters(
        base, year, counselling_type, counselling_state,
        quota_norm, allotted_category_norm, state, course_norm,
        rank_min, rank_max, search, course_type=course_type,
    )

    if round_display:
        rd_set = set(round_display)
        having_conds = []
        if "r1" in rd_set:
            having_conds.append(r1_count_expr > 0)
        if "r2" in rd_set:
            having_conds.append(r2_count_expr > 0)
        if "r3" in rd_set:
            having_conds.append(r3_count_expr > 0)
        if "r4" in rd_set:
            having_conds.append(r4_count_expr > 0)
        if having_conds:
            base = base.having(or_(*having_conds))

    if my_rank is not None:
        rd_set = set(round_display) if round_display else set()
        round_cond = ""
        if len(rd_set) == 1:
            r = next(iter(rd_set))
            if r == "r1":
                round_cond = " AND a2.round = 1"
            elif r == "r2":
                round_cond = " AND a2.round = 2"
            elif r == "r3":
                round_cond = " AND a2.round = 3"
            elif r == "r4":
                round_cond = " AND a2.round = 4"
        base = base.filter(
            sa_text(f"""EXISTS (
                SELECT 1 FROM allotments a2
                WHERE a2.rank = :my_rank
                  AND a2.year = allotments.year
                  AND a2.counselling_type = allotments.counselling_type
                  AND a2.institute_name = allotments.institute_name
                  AND a2.course_norm = allotments.course_norm
                  AND a2.quota_norm = allotments.quota_norm
                  AND a2.allotted_category_norm = allotments.allotted_category_norm
                  {round_cond}
            )""").bindparams(my_rank=my_rank)
        )

    # Institute profile range filters (HAVING on correlated subqueries)
    _annual_fee_cast = (
        "(SELECT CAST(i.annual_fee AS REAL) FROM institute_mapping m"
        " JOIN institutes i ON m.institute_code = i.institute_code"
        " WHERE m.db_institute_name = allotments.institute_name LIMIT 1)"
    )
    if fee_min is not None:
        base = base.having(literal_column(_annual_fee_cast) >= fee_min)
    if fee_max is not None:
        base = base.having(literal_column(_annual_fee_cast) <= fee_max)
    _bond_cast = f"CAST({_inst_sub.format(col='bond_forfeit')} AS REAL)"
    if bond_min is not None:
        base = base.having(literal_column(_bond_cast) >= bond_min)
    if bond_max is not None:
        base = base.having(literal_column(_bond_cast) <= bond_max)

    # Cast-wrapped subqueries for numeric sorting of string-stored columns
    _inst_sub_cast = (
        "(SELECT CAST(i.{col} AS REAL) FROM institute_mapping m"
        " JOIN institutes i ON m.institute_code = i.institute_code"
        " WHERE m.db_institute_name = allotments.institute_name LIMIT 1)"
    )
    sort_col_map = {
        "quota_norm": Allotment.quota_norm,
        "allotted_category_norm": Allotment.allotted_category_norm,
        "state": Allotment.state,
        "institute_name": Allotment.institute_name,
        "institute_pincode": Allotment.institute_pincode,
        "course_norm": Allotment.course_norm,
        "r1_closing_rank": r1_rank_expr,
        "r2_closing_rank": r2_rank_expr,
        "r3_closing_rank": r3_rank_expr,
        "r4_closing_rank": r4_rank_expr,
        "inst_fee_yr1": inst_fee_yr1,
        "inst_stipend_yr1": literal_column(_inst_sub_cast.format(col="stipend_yr1")),
        "inst_bond_forfeit": literal_column(_inst_sub_cast.format(col="bond_forfeit")),
    }
    sort_col = sort_col_map.get(sort_by, Allotment.institute_name)
    if sort_order == "desc":
        base = base.order_by(sort_col.desc().nullslast())
    else:
        base = base.order_by(sort_col.asc().nullslast())

    return base


# ---------------------------------------------------------------------------
# GET /closing-ranks/export  — CSV download (all matching rows, no pagination)
# ---------------------------------------------------------------------------

@router.get("/export")
def export_closing_ranks_csv(
    year: int = Query(2025),
    counselling_type: str = Query("AIQ"),
    counselling_state: Optional[str] = Query(None),
    quota_norm: Optional[List[str]] = Query(None),
    allotted_category_norm: Optional[List[str]] = Query(None),
    state: Optional[List[str]] = Query(None),
    course_norm: Optional[List[str]] = Query(None),
    course_type: Optional[List[str]] = Query(None),
    rank_min: Optional[int] = Query(None),
    rank_max: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    round_display: Optional[List[str]] = Query(None),
    my_rank: Optional[int] = Query(None),
    sort_by: str = Query("institute_name", enum=["quota_norm", "allotted_category_norm", "state", "institute_name", "institute_pincode", "course_norm", "r1_closing_rank", "r2_closing_rank", "r3_closing_rank", "r4_closing_rank", "inst_fee_yr1", "inst_stipend_yr1", "inst_bond_forfeit"]),
    sort_order: str = Query("asc", enum=["asc", "desc"]),
    fee_min: Optional[int] = Query(None),
    fee_max: Optional[int] = Query(None),
    bond_min: Optional[int] = Query(None),
    bond_max: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Export current filtered view as CSV (no row limit)."""
    base = _build_pivot_query(
        db, year, counselling_type, counselling_state,
        quota_norm, allotted_category_norm, state, course_norm,
        rank_min, rank_max, search, round_display, my_rank,
        sort_by, sort_order,
        fee_min=fee_min, fee_max=fee_max, bond_min=bond_min, bond_max=bond_max,
        course_type=course_type,
    )
    rows = base.all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        # Header — same order as table columns
        writer.writerow([
            "Quota", "Category", "State", "Institute", "Pincode", "Course",
            "Fee", "Stipend Y1", "Bond Years", "Bond Penalty", "Beds",
            "CR 2025 R1", "R1 Seats", "CR 2025 R2", "R2 Seats",
            "CR 2025 R3", "R3 Seats", "CR 2025 R4", "R4 Seats",
        ])
        yield buf.getvalue()

        for r in rows:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                r.quota_norm or "",
                r.allotted_category_norm or "",
                r.state or "",
                r.institute_name or "",
                r.institute_pincode or "",
                r.course_norm or "",
                r.inst_fee_yr1 if r.inst_fee_yr1 is not None else "",
                r.inst_stipend_yr1 or "",
                r.inst_bond_years or "",
                r.inst_bond_forfeit or "",
                r.inst_beds if r.inst_beds is not None else "",
                r.r1_closing_rank if r.r1_closing_rank is not None else "",
                r.r1_allotment_count or "",
                r.r2_closing_rank if r.r2_closing_rank is not None else "",
                r.r2_allotment_count or "",
                r.r3_closing_rank if r.r3_closing_rank is not None else "",
                r.r3_allotment_count or "",
                r.r4_closing_rank if r.r4_closing_rank is not None else "",
                r.r4_allotment_count or "",
            ])
            yield buf.getvalue()

    filename = f"neetpg_closing_ranks_{counselling_type}_{year}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /closing-ranks
# ---------------------------------------------------------------------------

@router.get("", response_model=ClosingRankListResponse)
def get_closing_ranks(
    # Dataset dimensions (default: AIQ 2025)
    year: int = Query(2025),
    counselling_type: str = Query("AIQ"),
    counselling_state: Optional[str] = Query(None),
    # Filters — all support multiple values via repeated params: ?state=Maharashtra&state=Tamil+Nadu
    quota_norm: Optional[List[str]] = Query(None),
    allotted_category_norm: Optional[List[str]] = Query(None),
    state: Optional[List[str]] = Query(None),
    course_norm: Optional[List[str]] = Query(None),
    course_type: Optional[List[str]] = Query(None),
    rank_min: Optional[int] = Query(None),
    rank_max: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    # Round filter: list of "r1"/"r2"/"r3"/"r4" (OR logic); None = all
    round_display: Optional[List[str]] = Query(None),
    # Rank search: show groups where closing rank >= my_rank (i.e. this rank could be allotted)
    my_rank: Optional[int] = Query(None),
    # Sort
    sort_by: str = Query("institute_name", enum=["quota_norm", "allotted_category_norm", "state", "institute_name", "institute_pincode", "course_norm", "r1_closing_rank", "r2_closing_rank", "r3_closing_rank", "r4_closing_rank", "inst_fee_yr1", "inst_stipend_yr1", "inst_bond_forfeit"]),
    sort_order: str = Query("asc", enum=["asc", "desc"]),
    # Institute profile range filters
    fee_min: Optional[int] = Query(None),
    fee_max: Optional[int] = Query(None),
    bond_min: Optional[int] = Query(None),
    bond_max: Optional[int] = Query(None),
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Return grouped closing-rank rows with R1 and R2 ranks pivoted into the same row.
    Closing rank is computed dynamically as MAX(rank) per group per round.
    """
    base = _build_pivot_query(
        db, year, counselling_type, counselling_state,
        quota_norm, allotted_category_norm, state, course_norm,
        rank_min, rank_max, search, round_display, my_rank,
        sort_by, sort_order,
        fee_min=fee_min, fee_max=fee_max, bond_min=bond_min, bond_max=bond_max,
        course_type=course_type,
    )

    # Total count
    total = base.count()
    pages = math.ceil(total / page_size) if page_size else 1
    offset = (page - 1) * page_size

    rows = base.offset(offset).limit(page_size).all()

    def _gid(r, round_num, count):
        if not count:
            return None
        return _encode_group_id(
            r.year, r.counselling_type, r.counselling_state,
            round_num, r.institute_name, r.institute_pincode,
            r.course_norm, r.quota_norm, r.allotted_category_norm,
        )

    data = [
        ClosingRankRow(
            r1_group_id=_gid(r, 1, r.r1_allotment_count),
            r2_group_id=_gid(r, 2, r.r2_allotment_count),
            r3_group_id=_gid(r, 3, r.r3_allotment_count),
            r4_group_id=_gid(r, 4, r.r4_allotment_count),
            year=r.year,
            counselling_type=r.counselling_type,
            counselling_state=r.counselling_state,
            institute_name=r.institute_name,
            institute_city=r.institute_city,
            institute_address=r.institute_address,
            institute_address_verified=r.institute_address_verified,
            institute_pincode=r.pincode_resolved,
            state=r.state,
            course_norm=r.course_norm,
            quota_norm=r.quota_norm,
            allotted_category_norm=r.allotted_category_norm,
            r1_closing_rank=r.r1_closing_rank,
            r1_allotment_count=r.r1_allotment_count or 0,
            r2_closing_rank=r.r2_closing_rank,
            r2_allotment_count=r.r2_allotment_count or 0,
            r3_closing_rank=r.r3_closing_rank,
            r3_allotment_count=r.r3_allotment_count or 0,
            r4_closing_rank=r.r4_closing_rank,
            r4_allotment_count=r.r4_allotment_count or 0,
            inst_fee_yr1=r.inst_fee_yr1,
            inst_fee_yr2=r.inst_fee_yr2,
            inst_fee_yr3=r.inst_fee_yr3,
            inst_stipend_yr1=r.inst_stipend_yr1,
            inst_stipend_yr2=r.inst_stipend_yr2,
            inst_stipend_yr3=r.inst_stipend_yr3,
            inst_bond_forfeit=r.inst_bond_forfeit,
            inst_bond_years=r.inst_bond_years,
            inst_beds=r.inst_beds,
            inst_university=r.inst_university,
            inst_matched=bool(r.inst_matched) if r.inst_matched is not None else None,
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

    # Extract group key fields (institute_city is NOT part of the key — only pincode)
    year = int(g["y"])
    counselling_type = g["ct"]
    counselling_state = g["cs"] or None
    round_ = int(g["r"])
    institute_name = g["i"] or None
    institute_pincode = g.get("ip") or None
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
            _eq_or_null(Allotment.institute_pincode, institute_pincode),
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
            r1_status=getattr(a, "r1_status", None),
            seat_outcome=getattr(a, "seat_outcome", None),
        )
        for a in allotments
    ]

    return DrillDownResponse(
        group_id=group_id,
        closing_rank=closing_rank,
        allotment_count=len(data),
        data=data,
    )
