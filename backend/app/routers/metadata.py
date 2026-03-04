"""
GET /metadata
Returns all distinct filter values available in the database.
Supports optional scoping by year, counselling_type, counselling_state, round.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, distinct, func

from ..database import get_db
from ..models import Allotment
from ..schemas import MetadataResponse

router = APIRouter()


@router.get("", response_model=MetadataResponse)
def get_metadata(
    year: Optional[int] = Query(None),
    counselling_type: Optional[str] = Query(None),
    counselling_state: Optional[str] = Query(None),
    round: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return all available filter values.
    Optionally scope to a specific dataset dimension.
    """
    base = db.query(Allotment)
    if year:
        base = base.filter(Allotment.year == year)
    if counselling_type:
        base = base.filter(Allotment.counselling_type == counselling_type)
    if counselling_state:
        base = base.filter(Allotment.counselling_state == counselling_state)
    if round:
        base = base.filter(Allotment.round == round)

    def _distinct(col):
        return [
            v for (v,) in base.with_entities(col).distinct().order_by(col).all()
            if v is not None
        ]

    years = _distinct(Allotment.year)
    counselling_types = _distinct(Allotment.counselling_type)
    counselling_states = _distinct(Allotment.counselling_state)
    rounds = _distinct(Allotment.round)
    quotas = _distinct(Allotment.quota_norm)
    categories = _distinct(Allotment.allotted_category_norm)
    states = _distinct(Allotment.state)
    courses = _distinct(Allotment.course_norm)

    return MetadataResponse(
        years=sorted(set(years)),
        counselling_types=sorted(set(counselling_types)),
        counselling_states=counselling_states,
        rounds=sorted(set(rounds)),
        quotas=sorted(set(quotas)),
        categories=sorted(set(categories)),
        states=sorted(set(states)),
        courses=sorted(set(courses)),
    )
