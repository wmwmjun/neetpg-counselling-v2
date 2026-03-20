"""
ORM models. Designed for zero-schema-rewrite extensibility:
  - Add year 2024 → new rows, same schema
  - Add state counselling → counselling_type='STATE', counselling_state='Karnataka'
  - Add rounds 2–4 → new rows, same schema
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, UniqueConstraint, Index
)
from .database import Base


class Allotment(Base):
    __tablename__ = "allotments"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Dataset dimensions (extensibility axes)
    year = Column(Integer, nullable=False)
    counselling_type = Column(String(64), nullable=False)   # AIQ | STATE
    counselling_state = Column(String(64), nullable=True)   # null for AIQ
    round = Column(Integer, nullable=False)

    # Source row fields
    sno = Column(Integer, nullable=True)
    rank = Column(Integer, nullable=True)

    # Quota
    quota_raw = Column(String(64), nullable=True)
    quota_norm = Column(String(64), nullable=True)

    # Institute
    institute_raw = Column(Text, nullable=True)
    institute_name = Column(String(256), nullable=True)
    institute_city = Column(String(128), nullable=True)
    institute_pincode = Column(String(10), nullable=True)
    state = Column(String(64), nullable=True)

    # Course
    course_raw = Column(Text, nullable=True)
    course_norm = Column(String(256), nullable=True)

    # Categories
    allotted_category_raw = Column(String(256), nullable=True)
    allotted_category_norm = Column(String(256), nullable=True)
    candidate_category_raw = Column(String(256), nullable=True)   # modal only

    # Extras
    remarks = Column(Text, nullable=True)
    source_page = Column(Integer, nullable=True)
    source_row_fingerprint = Column(String(64), nullable=True)

    # Round 2 specific fields
    # R1 outcome string parsed from the left half of the Round-2 PDF
    # (e.g. "Reported", "Not Reported", "Seat Surrendered")
    r1_status = Column(String(128), nullable=True)
    # Derived seat outcome after applying Round-1 × Round-2 business logic:
    # RETAINED | UPGRADED | LOST | FRESH | NOT_ALLOTTED | UNKNOWN
    seat_outcome = Column(String(64), nullable=True)
    # Option number from Round-2 PDF col 11 (stored but not exposed in UI)
    option_code = Column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "year", "counselling_type", "counselling_state",
            "round", "source_row_fingerprint",
            name="uq_allotment_fingerprint",
        ),
        Index("ix_allotments_year_round", "year", "round"),
        Index("ix_allotments_rank", "rank"),
        Index("ix_allotments_course_norm", "course_norm"),
        Index("ix_allotments_quota_norm", "quota_norm"),
        Index("ix_allotments_allotted_category_norm", "allotted_category_norm"),
        Index("ix_allotments_state", "state"),
        Index("ix_allotments_institute_name", "institute_name"),
    )


class InstituteMapping(Base):
    """Mapping from allotment institute names to institute_code (built by build_institutes_v2.py)."""
    __tablename__ = "institute_mapping"

    db_institute_name = Column(Text, primary_key=True)
    institute_code = Column(Integer, nullable=True)
    match_confidence = Column(String(64), nullable=True)
    match_score = Column(Integer, nullable=True)


class Institute(Base):
    """Institute data built from Seat Matrix + Profile PDF matching.
    Built by scripts/build_institutes_v2.py"""
    __tablename__ = "institutes"

    institute_code = Column(Integer, primary_key=True)
    institute_name = Column(String(256), nullable=False)
    display_name   = Column(String(320), nullable=False)
    address        = Column(Text, nullable=True)
    state          = Column(String(64), nullable=True)
    pincode        = Column(String(10), nullable=True)
    university     = Column(Text, nullable=True)
    fee_yr1        = Column(Integer, nullable=True)
    fee_yr2        = Column(Integer, nullable=True)
    fee_yr3        = Column(Integer, nullable=True)
    annual_fee     = Column(String(64), nullable=True)
    stipend_yr1    = Column(String(64), nullable=True)
    stipend_yr2    = Column(String(64), nullable=True)
    stipend_yr3    = Column(String(64), nullable=True)
    hostel_male    = Column(String(64), nullable=True)
    hostel_female  = Column(String(64), nullable=True)
    bond_forfeit   = Column(String(128), nullable=True)
    bond_years     = Column(String(64), nullable=True)
    beds           = Column(Integer, nullable=True)
    pwbd_friendly  = Column(String(64), nullable=True)
    website        = Column(String(256), nullable=True)
    match_status   = Column(String(64), nullable=True)


class RefCourse(Base):
    """Auto-populated from distinct course_norm after ingestion."""
    __tablename__ = "ref_courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_norm = Column(String(256), unique=True, nullable=False)
    degree = Column(String(32), nullable=True)
    specialty = Column(String(256), nullable=True)
    course_type = Column(String(32), nullable=True)   # Clinical | Non-Clinical | Para-Clinical | Pre-Clinical


class IngestionError(Base):
    """Stores rows that failed parsing/normalisation."""
    __tablename__ = "ingestion_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=True)
    counselling_type = Column(String(64), nullable=True)
    counselling_state = Column(String(64), nullable=True)
    round = Column(Integer, nullable=True)
    page_num = Column(Integer, nullable=True)
    row_data = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class IngestionProgress(Base):
    """Resume-safe progress tracker (one row per dataset)."""
    __tablename__ = "ingestion_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_key = Column(String(128), unique=True, nullable=False)
    last_page_completed = Column(Integer, default=0)
    total_rows_inserted = Column(Integer, default=0)
    total_rows_skipped = Column(Integer, default=0)
    status = Column(String(64), default="in_progress")   # in_progress | done | failed
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
