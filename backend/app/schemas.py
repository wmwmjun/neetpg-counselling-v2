"""
Pydantic v2 schemas for request/response validation.
"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class MetadataResponse(BaseModel):
    years: List[int]
    counselling_types: List[str]
    counselling_states: List[Optional[str]]
    rounds: List[int]
    quotas: List[str]
    categories: List[str]
    states: List[str]
    courses: List[str]


# ---------------------------------------------------------------------------
# Closing Rank (grouped)
# ---------------------------------------------------------------------------

class ClosingRankRow(BaseModel):
    group_id: str = Field(description="URL-safe base64 key for drill-down")
    year: int
    counselling_type: str
    counselling_state: Optional[str]
    round: int
    institute_name: Optional[str]
    state: Optional[str]
    course_norm: Optional[str]
    quota_norm: Optional[str]
    allotted_category_norm: Optional[str]
    closing_rank: Optional[int]
    allotment_count: int


class ClosingRankListResponse(BaseModel):
    data: List[ClosingRankRow]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Raw Allotment (for drill-down modal and /allotments endpoint)
# ---------------------------------------------------------------------------

class AllotmentRow(BaseModel):
    id: int
    year: int
    counselling_type: str
    counselling_state: Optional[str]
    round: int
    sno: Optional[int]
    rank: Optional[int]
    quota_raw: Optional[str]
    quota_norm: Optional[str]
    institute_raw: Optional[str]
    institute_name: Optional[str]
    state: Optional[str]
    course_raw: Optional[str]
    course_norm: Optional[str]
    allotted_category_raw: Optional[str]
    allotted_category_norm: Optional[str]
    candidate_category_raw: Optional[str]
    remarks: Optional[str]
    source_page: Optional[int]

    model_config = {"from_attributes": True}


class AllotmentListResponse(BaseModel):
    data: List[AllotmentRow]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Drill-down response
# ---------------------------------------------------------------------------

class DrillDownRow(BaseModel):
    rank: Optional[int]
    sno: Optional[int]
    round: int
    state: Optional[str]
    institute_name: Optional[str]
    course_norm: Optional[str]
    quota_norm: Optional[str]
    allotted_category_norm: Optional[str]
    candidate_category_raw: Optional[str]
    remarks: Optional[str]

    model_config = {"from_attributes": True}


class DrillDownResponse(BaseModel):
    group_id: str
    closing_rank: Optional[int]
    allotment_count: int
    data: List[DrillDownRow]
