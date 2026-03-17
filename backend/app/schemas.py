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
    course_types: List[str] = []   # Clinical, Non-Clinical, Para-Clinical, Pre-Clinical


# ---------------------------------------------------------------------------
# Closing Rank (grouped)
# ---------------------------------------------------------------------------

class ClosingRankRow(BaseModel):
    r1_group_id: Optional[str] = Field(None, description="URL-safe base64 key for R1 drill-down")
    r2_group_id: Optional[str] = Field(None, description="URL-safe base64 key for R2 drill-down")
    year: int
    counselling_type: str
    counselling_state: Optional[str]
    institute_name: Optional[str]
    institute_city: Optional[str] = None
    institute_address: Optional[str] = None        # PDF抽出住所 (clean_address/pdf_address)
    institute_address_verified: Optional[str] = None  # Claude調査済み住所
    institute_pincode: Optional[str] = None
    state: Optional[str]
    course_norm: Optional[str]
    quota_norm: Optional[str]
    allotted_category_norm: Optional[str]
    r1_closing_rank: Optional[int] = None
    r1_allotment_count: int = 0
    r2_closing_rank: Optional[int] = None
    r2_allotment_count: int = 0
    r3_closing_rank: Optional[int] = None
    r3_allotment_count: int = 0
    r3_group_id: Optional[str] = Field(None, description="URL-safe base64 key for R3 drill-down")
    r4_closing_rank: Optional[int] = None
    r4_allotment_count: int = 0
    r4_group_id: Optional[str] = Field(None, description="URL-safe base64 key for R4 drill-down")
    # Institute profile data (joined from institutes table via mapping)
    inst_fee_yr1: Optional[float] = None
    inst_fee_yr2: Optional[float] = None
    inst_fee_yr3: Optional[float] = None
    inst_stipend_yr1: Optional[str] = None
    inst_stipend_yr2: Optional[str] = None
    inst_stipend_yr3: Optional[str] = None
    inst_bond_forfeit: Optional[str] = None
    inst_bond_years: Optional[str] = None
    inst_beds: Optional[int] = None
    inst_university: Optional[str] = None
    inst_matched: Optional[bool] = None  # True if matched, False if unknown


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
    # Round 2 specific (null for Round 1 rows)
    r1_status: Optional[str] = None
    seat_outcome: Optional[str] = None

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
    # Round 2 specific (null for Round 1 rows)
    r1_status: Optional[str] = None
    seat_outcome: Optional[str] = None

    model_config = {"from_attributes": True}


class DrillDownResponse(BaseModel):
    group_id: str
    closing_rank: Optional[int]
    allotment_count: int
    data: List[DrillDownRow]


# ---------------------------------------------------------------------------
# Institutes
# ---------------------------------------------------------------------------

class InstituteRow(BaseModel):
    institute_code: int
    institute_name: str
    display_name: str
    address: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    university: Optional[str] = None
    fee_yr1: Optional[float] = None
    fee_yr2: Optional[float] = None
    fee_yr3: Optional[float] = None
    annual_fee: Optional[str] = None
    stipend_yr1: Optional[str] = None
    stipend_yr2: Optional[str] = None
    stipend_yr3: Optional[str] = None
    hostel_male: Optional[str] = None
    hostel_female: Optional[str] = None
    bond_forfeit: Optional[str] = None
    pwbd_friendly: Optional[str] = None
    website: Optional[str] = None
    match_status: Optional[str] = None

    model_config = {"from_attributes": True}


class InstituteListResponse(BaseModel):
    data: List[InstituteRow]
    total: int
    page: int
    page_size: int
    pages: int
