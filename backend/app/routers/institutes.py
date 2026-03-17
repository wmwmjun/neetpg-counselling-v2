"""
Institutes endpoint: list & detail for institute profile data.
"""
import math
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Institute
from ..schemas import InstituteRow, InstituteListResponse

router = APIRouter()


@router.get("", response_model=InstituteListResponse)
def get_institutes(
    # Filters
    search: Optional[str] = Query(None, description="Free-text search across name, address, state"),
    state: Optional[List[str]] = Query(None, description="Filter by state(s)"),
    match_status: Optional[List[str]] = Query(None, description="Filter by match status"),
    # Sort
    sort_by: str = Query(
        "display_name",
        enum=["display_name", "state", "pincode", "annual_fee", "stipend_yr1", "institute_code"],
    ),
    sort_order: str = Query("asc", enum=["asc", "desc"]),
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Institute)

    # Text search
    if search:
        term = f"%{search}%"
        q = q.filter(
            or_(
                Institute.display_name.ilike(term),
                Institute.institute_name.ilike(term),
                Institute.address.ilike(term),
                Institute.state.ilike(term),
                Institute.pincode.ilike(term),
                Institute.university.ilike(term),
            )
        )

    # State filter
    if state:
        q = q.filter(Institute.state.in_(state))

    # Match status filter
    if match_status:
        q = q.filter(Institute.match_status.in_(match_status))

    # Sorting
    sort_col_map = {
        "display_name": Institute.display_name,
        "state": Institute.state,
        "pincode": Institute.pincode,
        "annual_fee": Institute.annual_fee,
        "stipend_yr1": Institute.stipend_yr1,
        "institute_code": Institute.institute_code,
    }
    col = sort_col_map.get(sort_by, Institute.display_name)
    if sort_order == "desc":
        q = q.order_by(col.desc().nullslast())
    else:
        q = q.order_by(col.asc().nullsfirst())

    # Pagination
    total = q.count()
    pages = math.ceil(total / page_size) if page_size else 1
    records = q.offset((page - 1) * page_size).limit(page_size).all()

    return InstituteListResponse(
        data=[InstituteRow.model_validate(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{institute_code}", response_model=InstituteRow)
def get_institute(institute_code: int, db: Session = Depends(get_db)):
    """Get details for a specific institute by code."""
    inst = db.query(Institute).filter(
        Institute.institute_code == institute_code
    ).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institute not found")
    return InstituteRow.model_validate(inst)
